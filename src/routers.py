from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from .database import get_db
from sqlalchemy import text
from .schemas import ChatRequest, ChatResponse
from .rag.rag_chain import rag_chat,embedding_pipeline
from .lda.router import lda_router
from dotenv import load_dotenv
import os
from .embedding_task import start_scheduler
from contextlib import asynccontextmanager
from fastapi.responses import StreamingResponse

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
app = FastAPI(lifespan=lifespan)

allowed_origins = os.getenv("ALLOWED_CORS_ORIGINS").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
async def chat(req: ChatRequest):
    # Giả sử rag_chat trả về một async_generator
    answer = rag_chat(req.question) 

    return StreamingResponse(answer, media_type="text/plain")

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

