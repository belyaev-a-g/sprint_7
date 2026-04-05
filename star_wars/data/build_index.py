import os, logging
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader
from langchain_community.embeddings import SentenceTransformerEmbeddings
from huggingface_hub import snapshot_download
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams
from uuid import uuid4

# Загружаем документы
def create_vector_store(store_type):
    logging.info("Читаем документы...")
    snapshot_download("sentence-transformers/all-MiniLM-L6-v2")
    # Загрузка документов
    documents = []
    input_dir = "knowledge_base"
    for filename in os.listdir(input_dir):
        if filename.endswith(".txt"):
            file_path = os.path.join(input_dir, filename)
            loader = TextLoader(file_path, encoding="utf-8")
            current_documents = loader.load()
            documents.extend(current_documents)
            logging.info(f" {file_path}")
    logging.info(f"Прочитано {len(documents)} документов")


    # Разделение на чанки
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100,
        separators=["\n\n", "\n", "(?<=\\. )", " ", ""],
        keep_separator=False
    )
    chunks = text_splitter.split_documents(documents)

    for i, chunk in enumerate(chunks):
        chunk.metadata["chunk_index"] = i

    logging.info(f"Документы разбиты на {len(chunks)} чанков")

    collection_name = "knowledge_base"
    server_url = "http://localhost:6333"
    client = QdrantClient(url=server_url)

    if client.collection_exists(collection_name=collection_name):
        logging.info(f"Коллекция '{collection_name}' существует. Удаляем...")
        
        client.delete_collection(collection_name=collection_name)
        logging.info(f"Коллекция '{collection_name}' успешно удалена.")
    else:
        logging.info(f"Коллекция '{collection_name}' не найдена. Удаление не требуется.")

    client.create_collection(
         collection_name=collection_name,
         vectors_config=VectorParams(size=384, distance=Distance.COSINE),
    )

    # Создание эмбеддингов и векторного хранилища
    embeddings_path = "sentence-transformers/all-MiniLM-L6-v2"
    embeddings = SentenceTransformerEmbeddings(model_name=embeddings_path)

    vector_store = QdrantVectorStore(
        client=client,
        collection_name=collection_name,
        embedding=embeddings,
    )

    uuids = [i for i in range(len(chunks))]
    #uuids = [str(uuid4()) for _ in range(len(chunks))]
    vector_store.add_documents(documents=chunks, ids=uuids)
    logging.info(f"Загружено в Qdrant {len(chunks)} чанков")
    collection_info = client.get_collection(collection_name=collection_name)
    logging.info(f"Информация о коллекции {collection_info}")

    return vector_store

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        filename="../logs/build_index.log",
        filemode="a",
        format="%(asctime)s %(levelname)s %(message)s",
    )
    vector_store = create_vector_store("server")

