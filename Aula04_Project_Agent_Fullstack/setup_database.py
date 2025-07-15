from pymongo import MongoClient
from bson import json_util
from pymongo.operations import SearchIndexModel
import json
import time
import os
from datasets import load_dataset
from dotenv import load_dotenv

# Carrega variáveis de ambiente do arquivo .env
load_dotenv()

# Obtém a string de conexão do MongoDB Atlas
mongodb_uri = os.environ.get('MONGODB_ATLAS_URI')
if not mongodb_uri:
    print("ERROR: A variável de ambiente MONGODB_ATLAS_URI não está definida!")
    print("Por favor, verifique seu arquivo .env")
    exit(1)

print(f"Conectando ao MongoDB em: {mongodb_uri[:20]}...")

# Conecta ao MongoDB Atlas
try:
    client = MongoClient(mongodb_uri, appname="devrel.showcase.partner.openai")
    print("Conexão com MongoDB Atlas estabelecida com sucesso!")
except Exception as e:
    print(f"Erro ao conectar ao MongoDB Atlas: {e}")
    exit(1)

# Cria banco de dados e coleções
db = client['ai_airbnb']
print("\n=== Configurando coleção 'rentals' ===")

# Verifica se a coleção já existe
collection_names = db.list_collection_names()
if "rentals" in collection_names:
    print("A coleção 'rentals' já existe. Deseja recriá-la? (s/n)")
    choice = input().lower()
    if choice == 's':
        db.drop_collection("rentals")
        print("Coleção 'rentals' removida.")
    else:
        print("Usando coleção 'rentals' existente.")

# Cria a coleção se não existir ou foi removida
if "rentals" not in db.list_collection_names():
    db.create_collection("rentals")
    print("Coleção 'rentals' criada.")
    
    # Cria índice de pesquisa vetorial
    print("Criando índice de pesquisa vetorial...")
    search_index_model = SearchIndexModel(
        definition={
            "fields": [
                {
                    "type": "vector",
                    "numDimensions": 1536,
                    "path": "text_embeddings",
                    "similarity": "cosine"
                },
            ]
        },
        name="vector_index",
        type="vectorSearch",
    )
    result = db.rentals.create_search_index(model=search_index_model)
    print(f"Novo índice de pesquisa '{result}' está sendo construído.")
    
    # Aguarda até que o índice esteja pronto
    print("Verificando se o índice está pronto. Isso pode levar até um minuto.")
    predicate = lambda index: index.get("queryable") is True
    while True:
        indices = list(db.rentals.list_search_indexes(result))
        if len(indices) and predicate(indices[0]):
            break
        time.sleep(5)
        print(".", end="", flush=True)
    print(f"\nÍndice '{result}' está pronto para consultas.")
    
    # Carrega e ingere o dataset
    print("\nCarregando dataset do Hugging Face (MongoDB/airbnb_embeddings)...")
    try:
        dataset = load_dataset("MongoDB/airbnb_embeddings")
        print(f"Dataset carregado com sucesso! Total de registros: {len(dataset['train'])}")
        
        # Prepara os documentos para inserção
        insert_data = []
        count = 0
        total = len(dataset['train'])
        
        print(f"Importando {total} registros em lotes de 1000...")
        for i, item in enumerate(dataset['train']):
            # Converte o item do dataset para formato de documento MongoDB
            doc_item = json_util.loads(json_util.dumps(item))
            insert_data.append(doc_item)
            
            # Insere em lotes de 1000 documentos
            if len(insert_data) == 1000 or i == total - 1:
                db.rentals.insert_many(insert_data)
                count += len(insert_data)
                percentage = (count / total) * 100
                print(f"Progresso: {count}/{total} registros ({percentage:.1f}%)")
                insert_data = []
        
        print(f"Todos os {count} registros foram importados com sucesso!")
    except Exception as e:
        print(f"Erro ao carregar ou importar o dataset: {e}")

# Configura a coleção 'bookings'
print("\n=== Configurando coleção 'bookings' ===")
if "bookings" in db.list_collection_names():
    print("A coleção 'bookings' já existe. Deseja recriá-la? (s/n)")
    choice = input().lower()
    if choice == 's':
        db.drop_collection("bookings")
        print("Coleção 'bookings' removida.")
    else:
        print("Usando coleção 'bookings' existente.")

if "bookings" not in db.list_collection_names():
    db.create_collection("bookings")
    print("Coleção 'bookings' criada.")
    
    # Cria índice padrão para a coleção bookings
    print("Criando índice de pesquisa para 'bookings'...")
    search_index_model = SearchIndexModel(
        definition={
            "mappings": {
                "dynamic": True
            }
        },
        name="default"
    )
    
    result = db.bookings.create_search_index(model=search_index_model)
    print(f"Novo índice de pesquisa '{result}' está sendo construído.")
    
    # Aguarda até que o índice esteja pronto
    print("Verificando se o índice está pronto. Isso pode levar até um minuto.")
    predicate = lambda index: index.get("queryable") is True
    while True:
        indices = list(db.bookings.list_search_indexes(result))
        if len(indices) and predicate(indices[0]):
            break
        time.sleep(5)
        print(".", end="", flush=True)
    print(f"\nÍndice '{result}' está pronto para consultas.")

print("\n=== Configuração concluída ===")
print("O banco de dados 'ai_airbnb' foi configurado com sucesso.")
print("Você pode agora executar a aplicação com: python src/server/app.py")

client.close()
