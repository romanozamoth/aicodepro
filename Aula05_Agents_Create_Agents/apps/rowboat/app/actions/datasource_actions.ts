'use server';
import { redirect } from "next/navigation";
import { ObjectId, WithId } from "mongodb";
import { dataSourcesCollection, dataSourceDocsCollection } from "../lib/mongodb";
import { z } from 'zod';
import { GetObjectCommand, PutObjectCommand } from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";
import { projectAuthCheck } from "./project_actions";
import { WithStringId } from "../lib/types/types";
import { DataSourceDoc } from "../lib/types/datasource_types";
import { DataSource } from "../lib/types/datasource_types";
import { uploadsS3Client } from "../lib/uploads_s3_client";

export async function getDataSource(projectId: string, sourceId: string): Promise<WithStringId<z.infer<typeof DataSource>>> {
    await projectAuthCheck(projectId);
    const source = await dataSourcesCollection.findOne({
        _id: new ObjectId(sourceId),
        projectId,
    });
    if (!source) {
        throw new Error('Invalid data source');
    }
    const { _id, ...rest } = source;
    return {
        ...rest,
        _id: _id.toString(),
    };
}

export async function listDataSources(projectId: string): Promise<WithStringId<z.infer<typeof DataSource>>[]> {
    await projectAuthCheck(projectId);
    const sources = await dataSourcesCollection.find({
        projectId: projectId,
        status: { $ne: 'deleted' },
    }).toArray();
    return sources.map((s) => ({
        ...s,
        _id: s._id.toString(),
    }));
}

export async function createDataSource({
    projectId,
    name,
    data,
    status = 'pending',
}: {
    projectId: string,
    name: string,
    data: z.infer<typeof DataSource>['data'],
    status?: 'pending' | 'ready',
}): Promise<WithStringId<z.infer<typeof DataSource>>> {
    await projectAuthCheck(projectId);

    const source: z.infer<typeof DataSource> = {
        projectId: projectId,
        active: true,
        name: name,
        createdAt: (new Date()).toISOString(),
        attempts: 0,
        status: status,
        version: 1,
        data,
    };
    await dataSourcesCollection.insertOne(source);

    const { _id, ...rest } = source as WithId<z.infer<typeof DataSource>>;
    return {
        ...rest,
        _id: _id.toString(),
    };
}

export async function recrawlWebDataSource(projectId: string, sourceId: string) {
    await projectAuthCheck(projectId);

    const source = await getDataSource(projectId, sourceId);
    if (source.data.type !== 'urls') {
        throw new Error('Invalid data source type');
    }

    // mark all files as queued
    await dataSourceDocsCollection.updateMany({
        sourceId: sourceId,
    }, {
        $set: {
            status: 'pending',
            lastUpdatedAt: (new Date()).toISOString(),
            attempts: 0,
        }
    });

    // mark data source as pending
    await dataSourcesCollection.updateOne({
        _id: new ObjectId(sourceId),
    }, {
        $set: {
            status: 'pending',
            lastUpdatedAt: (new Date()).toISOString(),
            attempts: 0,
        },
        $inc: {
            version: 1,
        },
    });
}

export async function deleteDataSource(projectId: string, sourceId: string) {
    await projectAuthCheck(projectId);
    await getDataSource(projectId, sourceId);

    // mark data source as deleted
    await dataSourcesCollection.updateOne({
        _id: new ObjectId(sourceId),
    }, {
        $set: {
            status: 'deleted',
            lastUpdatedAt: (new Date()).toISOString(),
            attempts: 0,
        },
        $inc: {
            version: 1,
        },
    });

    redirect(`/projects/${projectId}/sources`);
}

export async function toggleDataSource(projectId: string, sourceId: string, active: boolean) {
    await projectAuthCheck(projectId);
    await getDataSource(projectId, sourceId);

    await dataSourcesCollection.updateOne({
        "_id": new ObjectId(sourceId),
        "projectId": projectId,
    }, {
        $set: {
            "active": active,
        }
    });
}

export async function addDocsToDataSource({
    projectId,
    sourceId,
    docData,
}: {
    projectId: string,
    sourceId: string,
    docData: {
        _id?: string,
        name: string,
        data: z.infer<typeof DataSourceDoc>['data']
    }[]
}): Promise<void> {
    await projectAuthCheck(projectId);
    await getDataSource(projectId, sourceId);

    await dataSourceDocsCollection.insertMany(docData.map(doc => {
        const record: z.infer<typeof DataSourceDoc> = {
            sourceId,
            name: doc.name,
            status: 'pending',
            createdAt: new Date().toISOString(),
            data: doc.data,
            version: 1,
        };
        if (!doc._id) {
            return record;
        }
        const recordWithId = record as WithId<z.infer<typeof DataSourceDoc>>;
        recordWithId._id = new ObjectId(doc._id);
        return recordWithId;
    }));

    await dataSourcesCollection.updateOne(
        { _id: new ObjectId(sourceId) },
        {
            $set: {
                status: 'pending',
                attempts: 0,
                lastUpdatedAt: new Date().toISOString(),
            },
            $inc: {
                version: 1,
            },
        }
    );
}

export async function listDocsInDataSource({
    projectId,
    sourceId,
    page = 1,
    limit = 10,
}: {
    projectId: string,
    sourceId: string,
    page?: number,
    limit?: number,
}): Promise<{
    files: WithStringId<z.infer<typeof DataSourceDoc>>[],
    total: number
}> {
    await projectAuthCheck(projectId);
    await getDataSource(projectId, sourceId);

    // Get total count
    const total = await dataSourceDocsCollection.countDocuments({
        sourceId,
        status: { $ne: 'deleted' },
    });

    // Fetch docs with pagination
    const docs = await dataSourceDocsCollection.find({
        sourceId,
        status: { $ne: 'deleted' },
    })
        .skip((page - 1) * limit)
        .limit(limit)
        .toArray();

    return {
        files: docs.map(f => ({ ...f, _id: f._id.toString() })),
        total
    };
}

export async function deleteDocsFromDataSource({
    projectId,
    sourceId,
    docIds,
}: {
    projectId: string,
    sourceId: string,
    docIds: string[],
}): Promise<void> {
    await projectAuthCheck(projectId);
    await getDataSource(projectId, sourceId);

    // mark for deletion
    await dataSourceDocsCollection.updateMany(
        {
            sourceId,
            _id: {
                $in: docIds.map(id => new ObjectId(id))
            }
        },
        {
            $set: {
                status: "deleted",
                lastUpdatedAt: new Date().toISOString(),
            },
            $inc: {
                version: 1,
            },
        }
    );

    // mark data source as pending
    await dataSourcesCollection.updateOne({
        _id: new ObjectId(sourceId),
    }, {
        $set: {
            status: 'pending',
            attempts: 0,
            lastUpdatedAt: new Date().toISOString(),
        },
        $inc: {
            version: 1,
        },
    });
}

export async function getDownloadUrlForFile(
    projectId: string,
    sourceId: string,
    fileId: string
): Promise<string> {
    await projectAuthCheck(projectId);
    await getDataSource(projectId, sourceId);

    // fetch s3 key for file
    const file = await dataSourceDocsCollection.findOne({
        sourceId,
        _id: new ObjectId(fileId),
        'data.type': 'file',
    });
    if (!file) {
        throw new Error('File not found');
    }
    if (file.data.type !== 'file') {
        throw new Error('File not found');
    }

    const command = new GetObjectCommand({
        Bucket: process.env.RAG_UPLOADS_S3_BUCKET,
        Key: file.data.s3Key,
    });

    return await getSignedUrl(uploadsS3Client, command, { expiresIn: 60 }); // URL valid for 1 minute
}

export async function getUploadUrlsForFilesDataSource(
    projectId: string,
    sourceId: string,
    files: { name: string; type: string; size: number }[]
): Promise<{
    fileId: string,
    presignedUrl: string,
    s3Key: string,
}[]> {
    await projectAuthCheck(projectId);
    const source = await getDataSource(projectId, sourceId);
    if (source.data.type !== 'files') {
        throw new Error('Invalid files data source');
    }

    const urls: {
        fileId: string,
        presignedUrl: string,
        s3Key: string,
    }[] = [];

    for (const file of files) {
        const fileId = new ObjectId().toString();
        const projectIdPrefix = projectId.slice(0, 2); // 2 characters from the start of the projectId
        const s3Key = `datasources/files/${projectIdPrefix}/${projectId}/${sourceId}/${fileId}/${file.name}`;
        // Generate presigned URL
        const command = new PutObjectCommand({
            Bucket: process.env.RAG_UPLOADS_S3_BUCKET,
            Key: s3Key,
            ContentType: file.type,
        });
        const presignedUrl = await getSignedUrl(uploadsS3Client, command, { expiresIn: 10 * 60 }); // valid for 10 minutes
        urls.push({
            fileId,
            presignedUrl,
            s3Key,
        });
    }

    return urls;
}
