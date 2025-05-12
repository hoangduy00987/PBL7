from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda
from dotenv import load_dotenv
from sqlalchemy import text
import os
import asyncio
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

dotenv_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
load_dotenv(dotenv_path=dotenv_path)
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
logging.basicConfig(level=logging.INFO)

def clean_value(value):
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return "null"
    return str(value).lower() if isinstance(value, str) else str(value)

def convert_from_postgres(db: Session = Depends(get_db)) -> list[Document]:
    query = "SELECT title, time, content, url  FROM paper WHERE time::timestamp >= (CURRENT_DATE - INTERVAL '1 day');"
    # query = "SELECT title, time, content, url  FROM paper WHERE time::timestamp >= '2025-05-08';"
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
        # print(f"Title: {title}")
    return documents



def create_vector_store(chunks: List[Document], db_path: str) -> Chroma:
    embedding_model = OpenAIEmbeddings(model="text-embedding-3-small")

    if os.path.exists(db_path) and os.listdir(db_path):
        db = Chroma(persist_directory=db_path, embedding_function=embedding_model)
        print("Loaded existing vector store.")
    else:
        db = Chroma.from_documents(documents=chunks, embedding=embedding_model, persist_directory=db_path)
        print("Created new vector store.")
        return db

    db.add_documents(chunks)
    print("Added documents to existing vector store.")
    return db

def is_within_time_window(paper_time: str, current_time: str,time_window: timedelta) -> bool:
    if not paper_time or not current_time:
        return False
    try:
        paper_time = datetime.strptime(paper_time,"%Y-%m-%d %H:%M:%S")
        time_dfference = current_time - paper_time
        return time_dfference <= time_window
    except ValueError:
        return False
def retrieve_context(db: Chroma, query: str,time_window:timedelta=timedelta(weeks=1)) -> List[Document]:
    retriever = db.as_retriever(search_type="similarity", search_kwargs={"k": 40})
    print("Relevant chunks are retrieved...\n")
    relevant_chunks = retriever.invoke(query)
    specific_date = extract_date_from_query(query)
    now =  datetime.now()
    if specific_date:
        filtered_chunks = [
            chunk for chunk in relevant_chunks if is_same_day(chunk.metadata["time"], specific_date)
        ]
    else:
        filtered_chunks = [
            chunk for chunk in relevant_chunks if is_within_time_window(chunk.metadata["time"], now, time_window)
        ]
        # print(relevant_chunks)
    return filtered_chunks

def is_same_day(paper_time: str, specific_date: datetime) -> bool:
    if not paper_time:
        return False
    try:
        paper_time = datetime.strptime(paper_time, "%Y-%m-%d %H:%M:%S")
        return paper_time.date() == specific_date.date()
    except ValueError:
        return False
    

def extract_date_from_query(query: str) -> str:
    date_pattern = r"(\d{1,2})[-/](\d{1,2})[-/](\d{4})"
    match = re.search(date_pattern, query)
    if match:
        day = int(match.group(1))
        month = int(match.group(2))
        year = int(match.group(3))
        return datetime(year, month, day)
    date_pattern_alt = r"Ngày (\d{1,2}) tháng (\d{1,2}) năm (\d{4})"
    match_alt = re.search(date_pattern_alt, query)
    if match_alt:
        day = int(match_alt.group(1))
        month = int(match_alt.group(2))
        year = int(match_alt.group(3))
        return datetime(year, month, day)
    return None
def data_chunks(text: List[Document]) -> List[Document]:
    print("Data file text is chunked...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = text_splitter.split_documents(text)
 
    return chunks


def build_context(relevant_chunks: List[Document]) -> List[Document]:
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
    print("=====", len(relevant_chunks))
    for chunk in relevant_chunks:
        # Lấy thời gian từ metadata của chunk
        time_info = chunk.metadata.get("time", "Không có thông tin thời gian")
        
        # In ra thông tin thời gian của chunk
        print(f"Chunk time: {time_info}")
    context = build_context(relevant_chunks)
    if "url" in query or "đường dẫn" in query or "link" in query:
        urls = []
        for chunk in relevant_chunks:
            url = chunk.metadata.get("url", None)
            if url:
                urls.append(url)
        
        return {"context": "\n".join(urls), "query": query}
    return {"context": context, "query": query}

async def rag_chat(question: str):
    db_path = "vector-store"
    context_data = get_context({"query": question, "db_path": db_path})
    context = context_data["context"]

    prompt_template = """Bạn là một trợ lý AI được huấn luyện để trả lời câu hỏi dựa trên thông tin cung cấp.

        - Chỉ sử dụng thông tin trong phần "Ngữ cảnh" để trả lời.
        - Trả lời một cách NGẮN GỌN, VẮN TẮT và đầy đủ ý chính như tóm tắt tin tức.
        - Nếu có nhiều thông tin liên quan, hãy liệt kê các điểm quan trọng.
        - Không đưa ra suy đoán hoặc thông tin ngoài ngữ cảnh.

        Câu hỏi: {query}

        Ngữ cảnh: {context}
        """


    rag_prompt = ChatPromptTemplate.from_template(prompt_template)
    formatted_prompt = rag_prompt.format_prompt(query=question, context=context)
    messages = formatted_prompt.to_messages()

    llm = ChatOpenAI(model="gpt-4o-mini")

    # Stream response
    stream = llm.astream(messages)

    async for chunk in stream:
        yield f"{chunk.content}"
