from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_qdrant import QdrantVectorStore, RetrievalMode
from qdrant_client import QdrantClient
from qdrant_client import models
import os
import requests

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

    results = vector_store.similarity_search(query, k=3)
    full_text = ""
    for res in results:
        print(f"* {res.page_content} [{res.metadata}]")
    for i, doc in enumerate(results):
        print(f"\nРезультат {i+1}:\n{doc.page_content}")
        print(f"\nSource: {doc.metadata["source"]}")
        
        window_size=20
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
        full_text = full_text + "\n\n".join([p.payload["page_content"] for p in sorted_points])

    print("full_text")
    print(full_text)
    print("full_text - DONE")
    return full_text


def generate_answer(query: str, context):

    API_KEY = os.getenv("YANDEX_API_KEY", "ваш_api_ключ_здесь")
    FOLDER_ID = os.getenv("YANDEX_FOLDER_ID", "ваш_folder_id_здесь")

    YANDEX_GPT_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    MODEL_URI = f"gpt://{FOLDER_ID}/yandexgpt/latest"

    context_text = "\n".join(context)

#Если ответа нет — скажи "Недостаточно данных".
    prompt = f"""
Ответь на вопрос, используя только контекст.

Контекст:
{context_text}

Вопрос:
{query}

"""

    headers = {
        "Authorization": f"Api-Key {API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "modelUri": MODEL_URI,
        "completionOptions": {
            "stream": False,
            "temperature": 0.3,
            "maxTokens": 300
        },
        "messages": [
            {
                "role": "user",
                "text": prompt
            }
        ]
    }

    response = requests.post(YANDEX_GPT_URL, headers=headers, json=data)
    print("response begin")
    print(response)
    print("response end")
    response.raise_for_status()

    result = response.json()
    return result["result"]["alternatives"][0]["message"]["text"]

def rag(query: str):
    context = retrieve(query)
    answer = generate_answer(query, context)

    print("=== QUERY ===")
    print(query)

    print("\n=== CONTEXT ===")
    for i, c in enumerate(context, 1):
        print(f"{i}. {c}")

    print("\n=== ANSWER ===")
    print(answer)

if __name__ == "__main__":
    vector_store = connect_to_vector_store("server")
    while True:
        print("Test knowledge base chat-bot!")
        query=input("Ask your question, or press enter to exit: ")
        if query == "":
            break
        context = search(vector_store, query)
        answer = generate_answer(query, context)
        print("answer")
        answer = generate_answer(query, context)
        print(answer)

