from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from .database import get_db
from sqlalchemy import text
from .chroma import ChatRequest, ChatResponse
from .rag.rag_chain import rag_chat,embedding_pipeline
from .lda.router import lda_router
from dotenv import load_dotenv
import os

load_dotenv()


app = FastAPI()

allowed_origins = os.getenv("ALLOWED_CORS_ORIGINS").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(lda_router)


@app.get("/papers")
def get_papers(db: Session = Depends(get_db)):
    result = db.execute(text("SELECT * FROM paper"))
    papers = result.mappings().all() 
    if not papers:
        raise HTTPException(status_code=404, detail="Paper table is empty")
    return papers


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    answer = rag_chat(req.question)
    return ChatResponse(answer=answer)


@app.get("/run-embedding")
async def run_embedding():
    try:
        print(f"Received request")
        embedding_pipeline()
        return {
            "status": "success",
            "message": "Embedding pipeline completed successfully!",
        }
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")
