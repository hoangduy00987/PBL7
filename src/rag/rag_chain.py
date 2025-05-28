from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda
from dotenv import load_dotenv
from sqlalchemy import text
import os
from typing import Union
from typing import List
import re
import difflib
import cohere
from langchain.schema import Document
from typing import Dict
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Chroma
from sqlalchemy.orm import Session
from ..database import get_db, SessionLocal
from fastapi import Depends
from datetime import datetime, timedelta
import logging
from langchain.memory import ConversationBufferWindowMemory
from langchain.schema import HumanMessage

dotenv_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
load_dotenv(dotenv_path=dotenv_path)
openai_api_key = os.getenv("OPENAI_API_KEY")
COHERE_API_KEY = os.getenv("COHERE_API_KEY")
co = cohere.Client(COHERE_API_KEY)

if openai_api_key is not None:
    os.environ["OPENAI_API_KEY"] = openai_api_key
# logging.basicConfig(level=logging.INFO)

def clean_value(value):
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return "null"
    return str(value).lower() if isinstance(value, str) else str(value)

def convert_from_postgres(db: Session = Depends(get_db)) -> list[Document]:
    query = "SELECT title, time, content, url  FROM paper WHERE time::timestamp >= (CURRENT_DATE - INTERVAL '1 day');"
    # query = "SELECT title, time, content, url  FROM paper WHERE time::timestamp >= '2025-05-13';"
    # query =  "SELECT title, time, content, url FROM paper"
    result = db.execute(text(query))

    documents = []
    for title, time, content, url in result.fetchall():
        title = clean_value(title)
        content = clean_value(content)
        url = clean_value(url)
        time = clean_value(time)

        metadata = {
            "title": title,
            "time": time,
            "url": url
        }

        doc = Document(page_content=content, metadata=metadata)
        documents.append(doc)
    return documents

def create_vector_store(chunks: List[Document], db_path: str, batch_size: int = 5000) -> Chroma:
    embedding_model = OpenAIEmbeddings(model="text-embedding-3-small")

    if os.path.exists(db_path) and os.listdir(db_path):
        db = Chroma(persist_directory=db_path, embedding_function=embedding_model)
        print("Loaded existing vector store.")
        
        # Chia nhỏ và thêm batch
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i+batch_size]
            db.add_documents(batch)
            logging.info(f"Added batch {i // batch_size + 1} to vector store.")
    else:
        # Nếu vector store chưa tồn tại, khởi tạo luôn với toàn bộ documents (nếu nhỏ hơn giới hạn)
        db = Chroma.from_documents(documents=chunks, embedding=embedding_model, persist_directory=db_path)
        print("Created new vector store.")
    return db


    
def retrieve_context(db: Chroma, query: str) -> List[Document]:
    retriever = db.as_retriever(search_type="similarity", search_kwargs={"k": 50})
    print("Relevant chunks are retrieved...\n")
    relevant_chunks = retriever.invoke(query)
    return relevant_chunks


def data_chunks(text: List[Document]) -> List[Document]:
    print("Data file text is chunked...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = text_splitter.split_documents(text)
 
    return chunks


def build_context(relevant_chunks: List[Document]) -> str:
    print("Context is built from relevant chunks")
    context = "\n\n".join([chunk.page_content for chunk in relevant_chunks])
    print(context)
    return context


def embedding_pipeline():
    logging.info("Starting embedding process from PostgreSQL...")
    db_path = "vector-store"
    with SessionLocal() as db:
        docs = convert_from_postgres(db)
        logging.info(f"Loaded {len(docs)} documents from PostgreSQL.")
        chunks = data_chunks(docs)
        logging.info(f"Split into {len(chunks)} text chunks.")
        create_vector_store(chunks, db_path)
        logging.info("Vector store created and saved successfully at:", db_path)
    logging.info("Embedding process completed.")


def get_context(inputs: Dict[str, str]) -> Dict[str, str]:
    query, db_path = inputs["query"], inputs["db_path"]
    print("Loadinngg the existing vector store\n")
    embedding_model = OpenAIEmbeddings(model="text-embedding-3-small")
    db = Chroma(persist_directory=db_path, embedding_function=embedding_model)
    relevant_chunks = retrieve_context(db, query)
    documents_text = [doc.page_content for doc in relevant_chunks]
    rerank_response = co.rerank(model='rerank-v3.5', query=query, documents=documents_text)
    reranked_indices = [item.index for item in rerank_response.results]
    top_10_indices = reranked_indices[:10]  
    top_10_docs = [relevant_chunks[i] for i in top_10_indices]
    for chunk in top_10_docs:
        time_info = chunk.metadata.get("time", "Không có thông tin thời gian")
        print(f"Thời gian của chunk: {time_info}")
    url = top_10_docs[0].metadata.get("url") if top_10_docs else ""
    print(f"========{url}")
    context = build_context(top_10_docs)
    return {"context": context, "query": query, "url": url if url is not None else ""}

def is_similar(a, b, threshold=0.85):
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio() >= threshold
# Hàm định dạng lịch sử hội thoại
def format_chat_history(chat_messages):
    result = "\n".join(
        f"Người dùng: {msg.content}" if isinstance(msg, HumanMessage)
        else f"Trợ lý: {msg.content}"
        for msg in chat_messages
    )
    print(result)
    return result


# Khởi tạo bộ nhớ ngoài hàm để giữ trạng thái liên tục
memory = ConversationBufferWindowMemory(
    k=5,
    memory_key="chat_history",
    return_messages=True
)
async def rag_chat(question: str):
    db_path = "vector-store"
    chat_messages = memory.load_memory_variables({})["chat_history"]

    # 1. Format lịch sử hội thoại
    chat_history_text = format_chat_history(chat_messages)

    # 2. Chuẩn hóa câu hỏi dựa vào lịch sử (nếu câu hỏi quá ngắn, mơ hồ)
    normalized_question = await clarify_question(question, chat_history_text)

    # 3. Truy vấn vector store với câu hỏi đã chuẩn hóa
    context_data = get_context({"query": normalized_question, "db_path": db_path})
    context = context_data.get("context", "").strip()
    url = context_data.get("url", "").strip()
    if not context:
        yield "Xin lỗi, mình không có đủ thông tin để trả lời câu hỏi này."
        return

    # 4. Tạo prompt với lịch sử + ngữ cảnh + câu hỏi chuẩn hóa
    prompt_template = """
    Bạn là một trợ lý AI thông minh. Dựa vào 'Ngữ cảnh' và 'Lịch sử hội thoại' dưới đây, hãy trả lời câu hỏi một cách ngắn gọn, chính xác và chỉ sử dụng thông tin trong ngữ cảnh đã cung cấp.

    - Nếu không có đủ thông tin trong ngữ cảnh, hãy trả lời: "Tôi không có đủ thông tin để trả lời câu hỏi này."
    - Không phỏng đoán hoặc đưa ra thông tin không có trong ngữ cảnh.
    - Tránh lặp lại toàn bộ câu hỏi trong câu trả lời.

    Lịch sử hội thoại:
    {chat_history}

    Ngữ cảnh:
    {context}

    Câu hỏi:
    {query}
    """



    rag_prompt = ChatPromptTemplate.from_template(prompt_template)
    formatted_prompt = rag_prompt.format_prompt(
        query=normalized_question,
        context=context,
        chat_history=chat_history_text
    )

    messages = formatted_prompt.to_messages()

    llm = ChatOpenAI(model="gpt-4o-mini")
    stream = llm.astream(messages)

    response_text = ""
    async for chunk in stream:
        if isinstance(chunk.content, str):
            response_text += chunk.content
            yield chunk.content
    if not is_similar(response_text.strip(), "Tôi không có đủ thông tin để trả lời câu hỏi này") and url:
        yield f"\n\nBạn có thể đọc chi tiết thông tin tại đây: {url}"

    memory.save_context({"input": question}, {"output": response_text})


async def clarify_question(question: str, chat_history_text: str) -> str:
    vague_words = ["vậy", "đội nào", "cái gì", "khi nào", "ở đâu","có những","ở trên","trước đó","trên","họ","này"]

    if any(w in question.lower() for w in vague_words):
        prompt = f"""Dựa trên lịch sử hội thoại dưới đây, hãy biến câu hỏi ngắn sau thành câu hỏi đầy đủ rõ nghĩa:
        Lịch sử hội thoại:
        {chat_history_text}

        Câu hỏi ngắn: {question}

        Câu hỏi đầy đủ:"""

        llm = ChatOpenAI(model="gpt-4o-mini")
        full_question_response = await llm.agenerate([[HumanMessage(content=prompt)]])
        return full_question_response.generations[0][0].text.strip()

    return question
