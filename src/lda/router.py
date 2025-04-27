from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from datetime import datetime
from ..database import get_db
from .lda_feature import get_topic_trends


lda_router = APIRouter(
    prefix="/lda",
    tags=["LDA"],
    responses={404: {"description": "Not found"}},
)

@lda_router.get("/topic-trends/")
async def fetch_topic_trends_in_month(month: int, year: int):
    try:
        current = datetime.now()
        if not month:
            month = current.month
        if not year:
            year = current.year
        
        trends = get_topic_trends(month=month, year=year)
        return trends
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
