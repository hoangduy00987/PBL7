from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda
from dotenv import load_dotenv
from sqlalchemy import text
import os
from typing import List
from langchain.schema import Document
from typing import Dict
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Chroma
from sqlalchemy.orm import Session
from ..database import get_db, SessionLocal
from fastapi import Depends


dotenv_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
load_dotenv(dotenv_path=dotenv_path)
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")


def convert_from_postgres(db: Session = Depends(get_db)) -> list[Document]:
    query = "SELECT title, time, content,url FROM paper"
    result = db.execute(text(query))

    documents = []
    for title, time, content,url in result.fetchall():
        metadata = {"title": title, "time": str(time), "url": url}
        doc = Document(page_content=content, metadata=metadata)
        documents.append(doc)
        print(f"Title: {title}")
    return documents


def create_vector_store(chunks: List[Document], db_path: str) -> Chroma:
    print("Chrome vector store is created...\n")
    embedding_model = OpenAIEmbeddings(model="text-embedding-3-small")
    db = Chroma.from_documents(
        documents=chunks, embedding=embedding_model, persist_directory=db_path
    )
    return db


def retrieve_context(db: Chroma, query: str) -> List[Document]:
    retriever = db.as_retriever(search_type="similarity", search_kwargs={"k": 5})
    print("Relevant chunks are retrieved...\n")
    relevant_chunks = retriever.invoke(query)
    # print(relevant_chunks)
    return relevant_chunks


def data_chunks(text: List[Document]) -> List[Document]:
    print("Data file text is chunked...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    chunks = text_splitter.split_documents(text)
    return chunks


def build_context(relevant_chunks: List[Document]) -> List[Document]:
    print("Context is built from relevant chunks")
    context = "\n\n".join([chunk.page_content for chunk in relevant_chunks])
    print(context)
    return context


def embedding_pipeline():
    print("Starting embedding process from PostgreSQL...")
    db_path = "vector-store"
    with SessionLocal() as db:
        docs = convert_from_postgres(db)
        print(f"Loaded {len(docs)} documents from PostgreSQL.")

        chunks = data_chunks(docs)
        print(f"Split into {len(chunks)} text chunks.")

        create_vector_store(chunks, db_path)
        print("Vector store created and saved successfully at:", db_path)


def get_context(inputs: Dict[str, str]) -> Dict[str, str]:
    query, db_path = inputs["query"], inputs["db_path"]
    print("Loadinngg the existing vector store\n")
    embedding_model = OpenAIEmbeddings(model="text-embedding-3-small")
    db = Chroma(persist_directory=db_path, embedding_function=embedding_model)
    relevant_chunks = retrieve_context(db, query)
    print("=====", len(relevant_chunks))
    context = build_context(relevant_chunks)
    if "url" in query or "đường dẫn" in query or "link" in query:
        urls = []
        for chunk in relevant_chunks:
            url = chunk.metadata.get("url", None)
            if url:
                urls.append(url)
        
        return {"context": "\n".join(urls), "query": query}
    return {"context": context, "query": query}

def rag_chat(question: str) -> str:
    prompt = """Bạn là một trợ lý AI được huấn luyện để trả lời câu hỏi dựa trên thông tin cung cấp.

    - Chỉ sử dụng thông tin trong phần "Ngữ cảnh" để trả lời.
    - Trả lời một cách NGẮN GỌN, VẮN TẮT và đầy đủ ý chính như tóm tắt tin tức.
    - Nếu như có nhiều tin tức khác nhau thì hãy liệt kê các tin tức đó ra 
    - Không thêm suy đoán hoặc thông tin bên ngoài.

    Câu hỏi: {query}

    Ngữ cảnh: {context}

    Nếu không thể tìm thấy câu trả lời trong ngữ cảnh, hãy trả lời:
    "Câu trả lời cho câu hỏi này không có trong nội dung đã cho."
    """

    rag_prompt = ChatPromptTemplate.from_template(prompt)
    llm = ChatOpenAI(model="gpt-4o-mini")

    str_parser = StrOutputParser()

    rag_chain = RunnableLambda(get_context) | rag_prompt | llm | str_parser
    current_dir = "vector-store"
    result = rag_chain.invoke({"query": question, "db_path": current_dir})
    return result
