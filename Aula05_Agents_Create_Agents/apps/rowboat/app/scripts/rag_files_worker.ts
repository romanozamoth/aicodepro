import '../lib/loadenv';
import { RecursiveCharacterTextSplitter } from "@langchain/textsplitters";
import { z } from 'zod';
import { dataSourceDocsCollection, dataSourcesCollection } from '../lib/mongodb';
import { EmbeddingRecord, DataSourceDoc, DataSource } from "../lib/types/datasource_types";
import { WithId } from 'mongodb';
import { embedMany } from 'ai';
import { embeddingModel } from '../lib/embedding';
import { qdrantClient } from '../lib/qdrant';
import { PrefixLogger } from "../lib/utils";
import { GoogleGenerativeAI } from "@google/generative-ai";
import { GetObjectCommand } from "@aws-sdk/client-s3";
import { uploadsS3Client } from '../lib/uploads_s3_client';
import crypto from 'crypto';

const splitter = new RecursiveCharacterTextSplitter({
    separators: ['\n\n', '\n', '. ', '.', ''],
    chunkSize: 1024,
    chunkOverlap: 20,
});

const second = 1000;
const minute = 60 * second;
const hour = 60 * minute;
const day = 24 * hour;

// Configure Google Gemini API
const genAI = new GoogleGenerativeAI(process.env.GOOGLE_API_KEY || '');

async function getFileContent(s3Key: string): Promise<Buffer> {
    const command = new GetObjectCommand({
        Bucket: process.env.RAG_UPLOADS_S3_BUCKET,
        Key: s3Key,
    });
    const response = await uploadsS3Client.send(command);
    const chunks: Uint8Array[] = [];
    for await (const chunk of response.Body as any) {
        chunks.push(chunk);
    }
    return Buffer.concat(chunks);
}

async function retryable<T>(fn: () => Promise<T>, maxAttempts: number = 3): Promise<T> {
    let attempts = 0;
    while (true) {
        try {
            return await fn();
        } catch (e) {
            attempts++;
            if (attempts >= maxAttempts) {
                throw e;
            }
        }
    }
}

async function runProcessPipeline(_logger: PrefixLogger, job: WithId<z.infer<typeof DataSource>>, doc: WithId<z.infer<typeof DataSourceDoc>>): Promise<void> {
    const logger = _logger
        .child(doc._id.toString())
        .child(doc.name);

    // Get file content from S3
    logger.log("Fetching file from S3");
    if (doc.data.type !== 'file') {
        throw new Error("Invalid data source type");
    }
    const fileData = await getFileContent(doc.data.s3Key);

    // Use Gemini to extract text content
    logger.log("Extracting content using Gemini");
    const model = genAI.getGenerativeModel({ model: "gemini-2.0-flash-001" });
    const prompt = "Extract and return only the text content from this document in markdown format. Exclude any formatting instructions or additional commentary.";
    
    const result = await model.generateContent([
        {
            inlineData: {
                data: fileData.toString('base64'),
                mimeType: doc.data.mimeType
            }
        },
        prompt
    ]);
    const markdown = result.response.text();

    // split into chunks
    logger.log("Splitting into chunks");
    const splits = await splitter.createDocuments([markdown]);

    // generate embeddings
    logger.log("Generating embeddings");
    const { embeddings } = await embedMany({
        model: embeddingModel,
        values: splits.map((split) => split.pageContent)
    });

    // store embeddings in qdrant
    logger.log("Storing embeddings in Qdrant");
    const points: z.infer<typeof EmbeddingRecord>[] = embeddings.map((embedding, i) => ({
        id: crypto.randomUUID(),
        vector: embedding,
        payload: {
            projectId: job.projectId,
            sourceId: job._id.toString(),
            docId: doc._id.toString(),
            content: splits[i].pageContent,
            title: doc.name,
            name: doc.name,
        },
    }));
    await qdrantClient.upsert("embeddings", {
        points,
    });

    // store content in doc record
    logger.log("Storing content in doc record");
    await dataSourceDocsCollection.updateOne({
        _id: doc._id,
        version: doc.version,
    }, {
        $set: {
            content: markdown,
            status: "ready",
            lastUpdatedAt: new Date().toISOString(),
        }
    });
}

async function runDeletionPipeline(_logger: PrefixLogger, job: WithId<z.infer<typeof DataSource>>, doc: WithId<z.infer<typeof DataSourceDoc>>): Promise<void> {
    const logger = _logger
        .child(doc._id.toString())
        .child(doc.name);

    // Delete embeddings from qdrant
    logger.log("Deleting embeddings from Qdrant");
    await qdrantClient.delete("embeddings", {
        filter: {
            must: [
                {
                    key: "projectId",
                    match: {
                        value: job.projectId,
                    }
                },
                {
                    key: "sourceId",
                    match: {
                        value: job._id.toString(),
                    }
                },
                {
                    key: "docId",
                    match: {
                        value: doc._id.toString(),
                    }
                }
            ],
        },
    });

    // Delete docs from db
    logger.log("Deleting doc from db");
    await dataSourceDocsCollection.deleteOne({ _id: doc._id });
}

// fetch next job from mongodb
(async () => {
    while (true) {
        console.log("Polling for job...")
        const now = Date.now();
        let job: WithId<z.infer<typeof DataSource>> | null = null;

        // first try to find a job that needs deleting
        job = await dataSourcesCollection.findOneAndUpdate({
            status: "deleted",
            $or: [
                { attempts: { $exists: false } },
                { attempts: { $lte: 3 } }
            ]
        }, { $set: { lastAttemptAt: new Date().toISOString() }, $inc: { attempts: 1 } }, { returnDocument: "after", sort: { createdAt: 1 } });

        if (job === null) {

            job = await dataSourcesCollection.findOneAndUpdate(
                {
                    $and: [
                        { 'data.type': { $eq: "files" } },
                        {
                            $or: [
                                // if the job has never been attempted
                                {
                                    status: "pending",
                                    attempts: 0,
                                },
                                // if the job was attempted but wasn't completed in the last hour
                                {
                                    status: "pending",
                                    lastAttemptAt: { $lt: new Date(now - 1 * hour).toISOString() },
                                },
                                // if the job errored out but hasn't been retried 3 times yet
                                {
                                    status: "error",
                                    attempts: { $lt: 3 },
                                },
                                // if the job errored out but hasn't been retried in the last 5 minutes
                                {
                                    status: "error",
                                    lastAttemptAt: { $lt: new Date(now - 1 * hour).toISOString() },
                                },
                            ]
                        }
                    ]
                },
                {
                    $set: {
                        status: "pending",
                        lastAttemptAt: new Date().toISOString(),
                    },
                    $inc: {
                        attempts: 1
                    },
                },
                { returnDocument: "after", sort: { createdAt: 1 } }
            );
        }

        if (job === null) {
            // if no doc found, sleep for a bit and start again
            await new Promise(resolve => setTimeout(resolve, 5 * second));
            continue;
        }

        const logger = new PrefixLogger(`${job._id.toString()}-${job.version}`);
        logger.log(`Starting job ${job._id}. Type: ${job.data.type}. Status: ${job.status}`);
        let errors = false;

        try {
            if (job.data.type !== 'files') {
                throw new Error("Invalid data source type");
            }

            if (job.status === "deleted") {
                // delete all embeddings for this source
                logger.log("Deleting embeddings from Qdrant");
                await qdrantClient.delete("embeddings", {
                    filter: {
                        must: [
                            { key: "projectId", match: { value: job.projectId } },
                            { key: "sourceId", match: { value: job._id.toString() } },
                        ],
                    },
                });

                // delete all docs for this source
                logger.log("Deleting docs from db");
                await dataSourceDocsCollection.deleteMany({
                    sourceId: job._id.toString(),
                });

                // delete the source record from db
                logger.log("Deleting source record from db");
                await dataSourcesCollection.deleteOne({
                    _id: job._id,
                });

                logger.log("Job deleted");
                continue;
            }

            // fetch docs that need updating
            const pendingDocs = await dataSourceDocsCollection.find({
                sourceId: job._id.toString(),
                status: { $in: ["pending", "error"] },
            }).toArray();

            logger.log(`Found ${pendingDocs.length} docs to process`);

            // for each doc
            for (const doc of pendingDocs) {
                try {
                    await runProcessPipeline(logger, job, doc);
                } catch (e: any) {
                    errors = true;
                    logger.log("Error processing doc:", e);
                    await dataSourceDocsCollection.updateOne({
                        _id: doc._id,
                        version: doc.version,
                    }, {
                        $set: {
                            status: "error",
                            error: e.message,
                        }
                    });
                }
            }

            // fetch docs that need to be deleted
            const deletedDocs = await dataSourceDocsCollection.find({
                sourceId: job._id.toString(),
                status: "deleted",
            }).toArray();

            logger.log(`Found ${deletedDocs.length} docs to delete`);

            for (const doc of deletedDocs) {
                try {
                    await runDeletionPipeline(logger, job, doc);
                } catch (e: any) {
                    errors = true;
                    logger.log("Error deleting doc:", e);
                    await dataSourceDocsCollection.updateOne({
                        _id: doc._id,
                        version: doc.version,
                    }, {
                        $set: {
                            status: "error",
                            error: e.message,
                        }
                    });
                }
            }
        } catch (e) {
            logger.log("Error processing job; will retry:", e);
            await dataSourcesCollection.updateOne({ _id: job._id, version: job.version }, { $set: { status: "error" } });
            continue;
        }

        // mark job as complete
        logger.log("Marking job as completed...");
        await dataSourcesCollection.updateOne({
            _id: job._id,
            version: job.version,
        }, {
            $set: {
                status: errors ? "error" : "ready",
                ...(errors ? { error: "There were some errors processing this job" } : {}),
            }
        });
    }
})();