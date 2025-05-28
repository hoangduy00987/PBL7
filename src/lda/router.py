from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from ..database import get_db
from .lda_feature import (get_topic_trends_week, get_topic_trends_month, get_topic_trends_quarter, get_topic_trends_year,
                          discover_popular_topics_today, discover_popular_topics_this_week, discover_popular_topics_this_month,
                          discover_hot_keywords
)
from .redis_cache import cache_redis, get_cache


lda_router = APIRouter(
    prefix="/lda",
    tags=["LDA"],
    responses={404: {"description": "Not found"}},
)


@lda_router.get("/topic-trends-week/")
async def fetch_topic_trends_in_week(start_date: str, end_date: str, db: Session = Depends(get_db)):
    try:
        current = datetime.now()
        # Calculate week boundaries (Monday to Sunday)
        week_start = current - timedelta(days=current.weekday())  # Monday
        week_end = week_start + timedelta(days=6)  # Sunday
        start_date = start_date or week_start.strftime("%Y-%m-%d")
        end_date = end_date or week_end.strftime("%Y-%m-%d")
        cache_key = f'trending-week:{start_date}-{end_date}'
        cached = get_cache(cache_key)
        if cached:
            print(f'Cache hit for {cache_key}')
            return cached
        
        print(f'Cache miss for {cache_key}, fetching from Database...')
        trends = get_topic_trends_week(start_date=start_date, end_date=end_date, db=db)
        
        cache_redis(cache_key, trends)
        
        return trends
    except Exception as e:
        print("Error when fetching topic trend week:", e)
        raise HTTPException(status_code=500, detail=str(e))


@lda_router.get("/topic-trends-month/")
async def fetch_topic_trends_in_month(month: int, year: int, db: Session = Depends(get_db)):
    try:
        current = datetime.now()
        month = month or current.month
        year = year or current.year
        
        cache_key = f'trending-month:{month}-{year}'
        cached = get_cache(cache_key)
        if cached:
            print(f'Cache hit for {cache_key}')
            return cached
        
        print(f'Cache miss for {cache_key}, fetching from Database...')
        trends = get_topic_trends_month(month=month, year=year, db=db)
        
        cache_redis(cache_key, trends)
        
        return trends
    except Exception as e:
        print("Error when fetching topic trend month:", e)
        raise HTTPException(status_code=500, detail=str(e))


@lda_router.get("/topic-trends-quarter/")
async def fetch_topic_trends_in_quarter(quarter: int, year: int, db: Session = Depends(get_db)):
    try:
        current = datetime.now()
        month = current.month
        if 1 <= month <= 3:
            quarter = quarter or 1
        elif 4 <= month <= 6:
            quarter = quarter or 2
        elif 7 <= month <= 9:
            quarter = quarter or 3
        else:
            quarter = quarter or 4
        
        year = year or current.year
        
        cache_key = f'trending-quarter:{quarter}-{year}'
        cached = get_cache(cache_key)
        if cached:
            print(f'Cache hit for {cache_key}')
            return cached
        
        print(f'Cache miss for {cache_key}, fetching from Database...')
        trends = get_topic_trends_quarter(quarter=quarter, year=year, db=db)
        
        cache_redis(cache_key, trends)
        
        return trends
    except Exception as e:
        print("Error when fetching topic trend quarter:", e)
        raise HTTPException(status_code=500, detail=str(e))


@lda_router.get("/topic-trends-year/")
async def fetch_topic_trends_in_year(year: int, db: Session = Depends(get_db)):
    try:
        current = datetime.now()
        year = year or current.year
        
        cache_key = f'trending-year:{year}'
        cached = get_cache(cache_key)
        if cached:
            print(f'Cache hit for {cache_key}')
            return cached
        
        print(f'Cache miss for {cache_key}, fetching from Database...')
        trends = get_topic_trends_year(year=year, db=db)
        
        cache_redis(cache_key, trends)
        
        return trends
    except Exception as e:
        print("Error when fetching topic trend year:", e)
        raise HTTPException(status_code=500, detail=str(e))


@lda_router.get("/popular-topics-today/")
async def fetch_popular_topics_today():
    try:
        cache_key = 'popular-topics-today'
        cached = get_cache(cache_key)
        if cached:
            print(f'Cache hit for {cache_key}')
            return cached
        
        print(f'Cache miss for {cache_key}, fetching from Database...')
        topics = discover_popular_topics_today()
        
        cache_redis(cache_key, topics)
        
        return topics
    except Exception as e:
        print("Error when fetching popular topics today:", e)
        raise HTTPException(status_code=500, detail=str(e))


@lda_router.get("/popular-topics-this-week/")
async def fetch_popular_topics_this_week():
    try:
        cache_key = 'popular-topics-this-week'
        cached = get_cache(cache_key)
        if cached:
            print(f'Cache hit for {cache_key}')
            return cached
        
        print(f'Cache miss for {cache_key}, fetching from Database...')
        topics = discover_popular_topics_this_week()
        
        cache_redis(cache_key, topics)
        
        return topics
    except Exception as e:
        print("Error when fetching popular topics this week:", e)
        raise HTTPException(status_code=500, detail=str(e))


@lda_router.get("/popular-topics-this-month/")
async def fetch_popular_topics_this_month():
    try:
        cache_key = 'popular-topics-this-month'
        cached = get_cache(cache_key)
        if cached:
            print(f'Cache hit for {cache_key}')
            return cached
        
        print(f'Cache miss for {cache_key}, fetching from Database...')
        topics = discover_popular_topics_this_month()
        
        cache_redis(cache_key, topics)
        
        return topics
    except Exception as e:
        print("Error when fetching popular topics this month:", e)
        raise HTTPException(status_code=500, detail=str(e))


@lda_router.get("/hot-keywords")
async def fetch_hot_keywords():
    try:
        cache_key = 'hot-keywords'
        cached = get_cache(cache_key)
        if cached:
            print(f'Cache hit for {cache_key}')
            return cached
        
        print(f'Cache miss for {cache_key}, fetching from Database...')
        results = discover_hot_keywords()
        
        cache_redis(cache_key, results)
        
        return results
    except Exception as e:
        print("Error when fetching popular topics this month:", e)
        raise HTTPException(status_code=500, detail=str(e))
