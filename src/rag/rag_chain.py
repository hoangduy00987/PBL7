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
from langchain.schema import Document
from typing import Dict
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Chroma
from sqlalchemy.orm import Session
from ..database import get_db, SessionLocal
from fastapi import Depends
from datetime import datetime, timedelta
import logging
from langchain.memory import ConversationBufferMemory
from .rerank import BGEHFReranker

memory = ConversationBufferMemory(memory_key="history", return_messages=True)
dotenv_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
load_dotenv(dotenv_path=dotenv_path)
openai_api_key = os.getenv("OPENAI_API_KEY")
if openai_api_key is not None:
    os.environ["OPENAI_API_KEY"] = openai_api_key
# logging.basicConfig(level=logging.INFO)

def clean_value(value):
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return "null"
    return str(value).lower() if isinstance(value, str) else str(value)

def convert_from_postgres(db: Session = Depends(get_db)) -> list[Document]:
    # query = "SELECT title, time, content, url  FROM paper WHERE time::timestamp >= (CURRENT_DATE - INTERVAL '1 day');"
    query = "SELECT title, time, content, url  FROM paper WHERE time::timestamp >= '2025-05-13';"
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
    reranker = BGEHFReranker(top_k=10)
    reranked_docs = reranker.compress_documents(relevant_chunks, query=query)
    for chunk in reranked_docs:
        time_info = chunk.metadata.get("time", "Không có thông tin thời gian")
        print(f"Thời gian của chunk: {time_info}")

    context = build_context(reranked_docs)
    return {"context": context, "query": query}




async def rag_chat(question: str):
    db_path = "vector-store"
    context_data = get_context({"query": question, "db_path": db_path})
    context = context_data["context"]
    llm = ChatOpenAI(model="gpt-4o-mini")
    prompt_template = ChatPromptTemplate.from_template("""
    Bạn là một trợ lý AI được huấn luyện để trả lời câu hỏi dựa trên thông tin cung cấp.

    - Chỉ sử dụng thông tin trong phần "Ngữ cảnh" và "Lịch sử hội thoại" để trả lời.
    - Trả lời NGẮN GỌN, RÕ RÀNG như tóm tắt tin tức.
    - Không đưa ra suy đoán hoặc thông tin ngoài ngữ cảnh.

    Lịch sử hội thoại:
    {history}

    Câu hỏi: {query}

    Ngữ cảnh: {context}
    """)
    # Lấy messages từ memory (history)
    memory_messages = memory.load_memory_variables({})["history"]

    # Format prompt
    formatted_prompt = prompt_template.format_messages(
        query=question,
        context=context,
        history=memory_messages
    )

    # Gọi LLM với stream
    stream = llm.astream(formatted_prompt)
    full_response = ""

    async for chunk in stream:
        if isinstance(chunk.content, str):
            full_response += chunk.content
            yield chunk.content


    # Cập nhật lại memory
    memory.chat_memory.add_user_message(question)
    memory.chat_memory.add_ai_message(full_response)

