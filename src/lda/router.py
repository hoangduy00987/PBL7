from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from datetime import datetime
from ..database import get_db
from .lda_feature import get_topic_trends
from .redis_cache import cache_redis, get_cache


lda_router = APIRouter(
    prefix="/lda",
    tags=["LDA"],
    responses={404: {"description": "Not found"}},
)

@lda_router.get("/topic-trends/")
async def fetch_topic_trends_in_month(month: int, year: int, db: Session = Depends(get_db)):
    try:
        current = datetime.now()
        month = month or current.month
        year = year or current.year
        
        cache_key = f'trending:{month}-{year}'
        cached = get_cache(cache_key)
        if cached:
            print(f'Cache hit for {cache_key}')
            return cached
        
        print(f'Cache miss for {cache_key}, fetching from Database...')
        trends = get_topic_trends(month=month, year=year, db=db)
        
        cache_redis(cache_key, trends)
        
        return trends
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
