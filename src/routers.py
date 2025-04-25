from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session
from .database import get_db
from sqlalchemy import text
from .chroma import ChatRequest, ChatResponse
from .rag.rag_chain import rag_chat,embedding_pipeline


app = FastAPI()


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
