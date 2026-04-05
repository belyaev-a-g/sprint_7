from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_qdrant import QdrantVectorStore, RetrievalMode
from qdrant_client import QdrantClient
from qdrant_client import models
import os
import requests
import re

def basic_injection_check(text: str) -> bool:
    # Паттерны, характерные для попыток перехвата управления моделью
    injection_patterns = [
        r"ignore (all )?previous instructions",
        r"Ignore all instructions",
        r"забудь (все )?предыдущие инструкции",
        r"system (prompt|message):",
        r"ты больше не",
        r"теперь ты —",
        r"отвечай как",
        r"DAN mode" # Классический пример из интернета
    ]
    
    for pattern in injection_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return False # Подозрение на инъекцию
    return True

def is_content_safe(text: str) -> bool:
    # 1. Список запрещенных паттернов (регулярные выражения)
    forbidden_patterns = [
        r"пароль", r"password",         # Попытки выудить учетные данные
        r"http[s]?://\S+",              # Ссылки (если они запрещены в базе)
        r"sql injection", r"DROP TABLE", # Технические атаки
        r"оскорбление_1", r"мат_1"       # Список обсценной лексики
    ]
    
    # 2. Очистка текста для проверки
    clean_text = text.lower().strip()
    
    # 3. Проверка на вхождение
    for pattern in forbidden_patterns:
        if re.search(pattern, clean_text):
            return False
            
    # 4. Проверка на длину (слишком короткие или длинные чанки могут быть мусором)
    if len(clean_text) < 10:
        return False
        
    return True

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

    results = vector_store.similarity_search(query, k=1)
    full_text = ""
    for i, doc in enumerate(results):
        
        window_size=5
        source = doc.metadata["source"]
        current_idx = doc.metadata["_id"]
        current_chunk_idx = doc.metadata["chunk_index"]
        start_idx = max(0, current_idx - window_size)
        end_idx = current_idx + window_size
        source_file = doc.metadata.get("source")

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

        sorted_points = sorted(window_chunks, key=lambda x: x.payload["metadata"]["chunk_index"])

        full_text = full_text + "\n\n".join([p.payload["page_content"] for p in sorted_points])
        full_text = full_text + "\n\n" + "Источник:" + source_file

    return full_text


def generate_answer(query: str, context, safety_mode: str):

    API_KEY = os.getenv("YANDEX_API_KEY", "ваш_api_ключ_здесь")
    FOLDER_ID = os.getenv("YANDEX_FOLDER_ID", "ваш_folder_id_здесь")

    YANDEX_GPT_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    #MODEL_URI = f"gpt://{FOLDER_ID}/yandexgpt-lite/latest"
    MODEL_URI = f"gpt://{FOLDER_ID}/yandexgpt/latest"

    safety_policy = ""

    make_post_check = False
    match safety_mode.strip().lower():
        case "pre-prompt":
            if not is_content_safe(context): 
                return f"Предупреждение: исходный файл заблокирован фильтром безопасности."
        case "post-check":
            make_post_check = True
        case "block":
            if not basic_injection_check(query): 
                return f"Предупреждение: запрос заблокирован фильтром безопасности."
            if not basic_injection_check(context): 
                return f"Предупреждение: контекст заблокирован фильтром безопасности."
        case _:
            return "Значение не распознано (аналог default)"

    context_text = "\n".join(context)

    prompt = f"""
Ты RAG-помощник по внутренней базе знаний. 
Ответь на вопрос, используя только контекст.
Если данных недостаточно, отвечай строго: 'Я не знаю'. 
В конце перечисли источники.
Сначала покажи краткие шаги рассуждения (CoT в явном виде), затем дай ответ. 
{safety_policy}

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
    response.raise_for_status()

    result = response.json()

    llm_answer = result["result"]["alternatives"][0]["message"]["text"]

    if make_post_check:
        if not basic_injection_check(llm_answer): 
            return f"Предупреждение: ответ от модели заблокирован фильтром безопасности."
        if not basic_injection_check(llm_answer): 
            return f"Предупреждение: ответ от модели заблокирован фильтром безопасности."

    return llm_answer

if __name__ == "__main__":
    vector_store = connect_to_vector_store("server")
    while True:
        print("Test knowledge base chat-bot!")
        query=input("Ask your question, or press enter to exit: ")
        if query == "":
            break
        context = search(vector_store, query)
        print("pre-prompt answer")
        answer = generate_answer(query, context, "pre-prompt")
        print(answer)
        print("post-check answer")
        answer = generate_answer(query, context, "post-check")
        print(answer)
        print("block instructions answer")
        answer = generate_answer(query, context, "block")
        print(answer)

