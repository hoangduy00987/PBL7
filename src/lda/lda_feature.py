from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from ..database import get_db, engine
import pandas as pd
from datetime import datetime


def get_topic_trends(month: int, year: int, db: Session = Depends(get_db)):
    # Kết nối cơ sở dữ liệu và lấy dữ liệu
    with engine.connect() as conn:
        sql_query = text("SELECT * FROM paper WHERE time LIKE :time_pattern")
        result = conn.execute(sql_query, {"time_pattern": f"{year}-{month:02d}%"})
        df = pd.DataFrame(result.fetchall(), columns=result.keys())
    
    if df.empty:
        return {
            "month": month,
            "year": year,
            "topics": [],
            "data": [],
            "keywords": {}
        }

    # Xử lý thời gian
    df['time'] = pd.to_datetime(df['time'], format='%Y-%m-%d %H:%M:%S')
    df['year'] = df['time'].dt.year
    df['month'] = df['time'].dt.month
    df['day'] = df['time'].dt.day
    # df.loc[df['keyword'].isin(['NaN', 'Null']), 'keyword'] = df['category']

    df['Topic'] = df['topic']
    df['Topic_Name'] = df['topic_name']

    keywords_data = {}
    result = db.execute(
        text("""
            SELECT topic_name, keyword, value, category
            FROM topic_keywords
            WHERE year = :year AND month = :month
            ORDER BY topic_name, value DESC
        """),
        {"year": year, "month": month}
    )
    for row in result:
        topic_name = row[0]
        if topic_name not in keywords_data:
            keywords_data[topic_name] = []
        keywords_data[topic_name].append({
            "text": row[1],
            "value": row[2],
            "category": row[3]
        })

    # Phân tích xu hướng theo ngày
    month_data = df[(df['month'] == month) & (df['year'] == year)]
    trend_data = month_data.groupby(['year', 'month', 'day', 'Topic_Name']).size().unstack(fill_value=0)
    trend_data = trend_data.div(trend_data.sum(axis=1), axis=0) * 100  # Chuyển sang phần trăm

    # Tạo danh sách nhãn chủ đề
    topics = trend_data.columns.tolist()

    # Tạo dữ liệu JSON
    data = []
    for (y, m, d), row in trend_data.iterrows():
        date_str = f"{int(d):02d}"
        full_date = datetime(year, month, int(d)).strftime("%B %d, %Y")
        percentages = {topic: round(float(row[topic]), 1) for topic in topics}
        data.append({
            "date": date_str,
            "fullDate": full_date,
            "percentages": percentages
        })

    return {
        "month": month,
        "year": year,
        "topics": topics,
        "data": data,
        "keywords": keywords_data
    }
