from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from datetime import datetime
from ..database import get_db, SessionLocal
from .lda_feature import fetch_trend_in_month


lda_router = APIRouter(
    prefix="/lda",
    tags=["LDA"],
    responses={404: {"description": "Not found"}},
)

@lda_router.get("/trend/")
def get_trend(month: int, year: int, db: Session = Depends(get_db)):
    current = datetime.now()
    if not month:
        month = current.month
    if not year:
        year = current.year
    
    trend = fetch_trend_in_month(month=month, year=year, db=db)
    return trend
