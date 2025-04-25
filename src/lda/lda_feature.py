from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from ..database import get_db, SessionLocal


def fetch_trend_in_month(month: int, year: int, db: Session = Depends(get_db)):
    query = """
    SELECT * FROM paper where time like '%s-%s-%'
    """(year, month)
    results = db.execute(text(query))
    trends = results.mappings().all()
    return trends
