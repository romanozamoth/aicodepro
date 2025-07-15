import pinecone
from pinecone import Pinecone
import openai
import os
from dotenv import load_dotenv

# Carregar variáveis do arquivo .env
load_dotenv()

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Configuração do Pinecone (nova API)
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index("bugflow")  # Nome do índice criado no painel

# Função para indexar chamados no Pinecone
def indexar_chamado(chamado_id, descricao):
    embedding = openai.Embedding.create(
        input=descricao, model="text-embedding-ada-002", api_key=OPENAI_API_KEY
    )["data"][0]["embedding"]
    index.upsert(vectors=[(str(chamado_id), embedding)])
    print(f"Chamado {chamado_id} indexado com sucesso no Pinecone.")

# Função para buscar chamados similares
def buscar_chamados_similares(descricao):
    embedding = openai.Embedding.create(
        input=descricao, model="text-embedding-ada-002", api_key=OPENAI_API_KEY
    )["data"][0]["embedding"]
    resultados = index.query(vector=embedding, top_k=5, include_metadata=True)
    print("Chamados similares encontrados:", resultados)
    return resultados["matches"]
