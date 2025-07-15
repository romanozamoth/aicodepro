# -*- coding: utf-8 -*-
import os
import pinecone
import psycopg2
from dotenv import load_dotenv
from openai import OpenAI
from pathlib import Path

dotenv_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=dotenv_path)

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
NEON_DB_URL = os.getenv("NEON_DB_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Inicializar Pinecone corretamente (nova API v3.0+)
pc = pinecone.Pinecone(api_key=PINECONE_API_KEY)

# Usar o índice já criado manualmente
index_name = "bugflow"

# Listar indices existentes para verificar
existing_indexes = [idx.name for idx in pc.list_indexes()]  # Nova sintaxe para v3.0+

if index_name not in existing_indexes:
    print(f"ERRO: O índice '{index_name}' não foi encontrado. Por favor, crie-o manualmente no console do Pinecone.")
    print(f"Índices disponíveis: {existing_indexes}")
    exit(1)
else:
    print(f"Usando índice existente: '{index_name}'")

# Obter referencia ao indice (nova sintaxe para v3.0+)
print(f"Conectando ao índice '{index_name}'...")
index = pc.Index(index_name)

# Inicializar OpenAI
client = OpenAI(api_key=OPENAI_API_KEY)

# Funcao para obter bugs do NeonDB
def buscar_bugs_do_neon():
    query = "SELECT id, descricao, passos_reproducao, versao_sistema, ambiente FROM bugs WHERE status = 'Aberto';"
    try:
        conn = psycopg2.connect(NEON_DB_URL)
        cur = conn.cursor()
        cur.execute(query)
        bugs = cur.fetchall()
        cur.close()
        conn.close()
        return [{
            "id": row[0], 
            "descricao": row[1],
            "passos_reproducao": row[2] if row[2] else "",
            "versao": row[3] if row[3] else "",
            "ambiente": row[4] if row[4] else ""
        } for row in bugs]
    except Exception as e:
        print("Erro ao buscar bugs do NeonDB:", str(e))
        return []

# Funcao para indexar bugs no Pinecone
def indexar_bugs_no_pinecone():
    bugs = buscar_bugs_do_neon()
    if not bugs:
        print("Nenhum bug encontrado para indexacao.")
        return

    vectors = []
    for bug in bugs:
        # Criar texto enriquecido para melhor contexto semantico
        texto_completo = f"Bug: {bug['descricao']}\n"
        if bug['passos_reproducao']:
            texto_completo += f"Passos para reproducao: {bug['passos_reproducao']}\n"
        if bug['versao']:
            texto_completo += f"Versao: {bug['versao']}\n"
        if bug['ambiente']:
            texto_completo += f"Ambiente: {bug['ambiente']}"
            
        response = client.embeddings.create(input=texto_completo, model="text-embedding-ada-002")
        embedding = response.data[0].embedding

        # Adicionar metadados para facilitar a busca
        metadata = {
            "descricao": bug['descricao'],
            "versao": bug['versao'],
            "ambiente": bug['ambiente']
        }
        
        vectors.append((str(bug["id"]), embedding, metadata))

    index.upsert(vectors=vectors)
    print(f"{len(bugs)} bugs indexados no Pinecone com sucesso.")


# Executar a indexacao
if __name__ == "__main__":
    indexar_bugs_no_pinecone()
