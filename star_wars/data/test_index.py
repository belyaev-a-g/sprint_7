from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_qdrant import QdrantVectorStore, RetrievalMode
from qdrant_client import QdrantClient
from qdrant_client import models

def connect_to_vector_store(store_type):
    collection_name = "knowledge_base"
    server_url = "http://localhost:6333"
    client = QdrantClient(url=server_url)

    embeddings_path = "sentence-transformers/all-MiniLM-L6-v2"
    embeddings = SentenceTransformerEmbeddings(model_name=embeddings_path)

    vector_store = QdrantVectorStore(
        client=client,
        collection_name=collection_name,
        embedding=embeddings,
        retrieval_mode=RetrievalMode.DENSE,
    )

    return vector_store

def search(vector_store, query):

    results = vector_store.similarity_search(query, k=5)
    for res in results:
        print(f"* {res.page_content} [{res.metadata}]")
    for i, doc in enumerate(results):
        print(f"\nРезультат {i+1}:\n{doc.page_content}")
        print(f"\nSource: {doc.metadata["source"]}")
        
        window_size=5
        source = doc.metadata["source"]
        current_idx = doc.metadata["_id"]
        current_chunk_idx = doc.metadata["chunk_index"]
        start_idx = max(0, current_idx - window_size)
        end_idx = current_idx + window_size
        source_file = doc.metadata.get("source")
        print(f"\ncurrent_idx: {current_idx}")
        print(f"\nstart_idx: {start_idx}")
        print(f"\nend_idx: {end_idx}")
        print(f"\nsource_file: {source_file}")
        print(f"\ncurrent_chunk_idx: {current_chunk_idx}")
 

        # Если vector_store инициализирован через LangChain:
        # vector_store = QdrantVectorStore(client=client, collection_name="...", ...)

        # 3. Запрос через атрибут .client
        window_chunks, _ = vector_store.client.scroll(
            collection_name="knowledge_base",
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(key="metadata.source", match=models.MatchValue(value=source_file)),
                    models.FieldCondition(
                        key="metadata.chunk_index", 
                        range=models.Range(gte=start_idx, lte=end_idx)
                    ) 
                ]
            ),
            with_payload=True
        )  

        print("len(window_chunks)")
        print(len(window_chunks))
    
        # 4. Сортируем по индексу, так как scroll возвращает их в случайном порядке
        sorted_points = sorted(window_chunks, key=lambda x: x.payload["metadata"]["chunk_index"])

        # 5. Собираем итоговый текст
        full_text = "\n\n".join([p.payload["page_content"] for p in sorted_points])
        print("full_text")
        print(full_text)


if __name__ == "__main__":
    vector_store = connect_to_vector_store("server")
    while True:
        print("Test knowledge base chat-bot!")
        query=input("Ask your question, or press enter to exit: ")
        if query == "":
            break
        search(vector_store, query)

