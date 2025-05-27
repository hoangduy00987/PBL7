from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from ..database import get_db, engine
import pandas as pd
from datetime import datetime


def get_topic_trends_month(month: int, year: int, db: Session = Depends(get_db)):
    # Kết nối cơ sở dữ liệu và lấy dữ liệu
    with engine.connect() as conn:
        # sql_query = text("SELECT * FROM paper WHERE time LIKE :time_pattern")
        sql_query = text("""
            SELECT
                p.id, 
                p.source, 
                p.url, 
                p.category, 
                p.keyword, 
                p.time, 
                p.title, 
                p.content, 
                p.tokens, 
                tm.topic_name, 
                tm.topic 
            FROM paper p 
            JOIN topic_month tm ON tm.paper_id = p.id
            WHERE p.time LIKE :time_pattern
        """)
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


def get_topic_trends_week(start_date: str, end_date: str, db: Session = Depends(get_db)):
    # Kết nối cơ sở dữ liệu và lấy dữ liệu
    with engine.connect() as conn:
        sql_query = text("""
            SELECT
                p.id, 
                p.source, 
                p.url, 
                p.category, 
                p.keyword, 
                p.time, 
                p.title, 
                p.content, 
                p.tokens, 
                tw.topic_name, 
                tw.topic 
            FROM paper p 
            JOIN topic_week tw ON tw.paper_id = p.id
            WHERE CAST(p.time AS TIMESTAMP) BETWEEN :start_date AND :end_date
        """)
        result = conn.execute(sql_query, {"start_date": f"{start_date} 00:00:00", "end_date": f"{end_date} 23:59:59"})
        df = pd.DataFrame(result.fetchall(), columns=result.keys())
    
    if df.empty:
        return {
            "start_date": start_date,
            "end_date": end_date,
            "topics": [],
            "data": [],
            "keywords": {}
        }

    # Xử lý thời gian
    df['time'] = pd.to_datetime(df['time'], format='%Y-%m-%d %H:%M:%S')
    df['year'] = df['time'].dt.year
    df['month'] = df['time'].dt.month
    df['day'] = df['time'].dt.day
    df['Topic'] = df['topic']
    df['Topic_Name'] = df['topic_name']

    keywords_data = {}
    result = db.execute(
        text("""
            SELECT topic_name, keyword, value, category
            FROM topic_keywords_week
            WHERE start_date = :start_date AND end_date = :end_date
            ORDER BY topic_name, value DESC
        """),
        {"start_date": start_date, "end_date": end_date}
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

    # Phân tích xu hướng theo ngày trong khoảng thời gian
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    week_data = df[(df['time'] >= start_dt) & (df['time'] <= end_dt + pd.Timedelta(days=1) - pd.Timedelta(seconds=1))]
    trend_data = week_data.groupby(['year', 'month', 'day', 'Topic_Name']).size().unstack(fill_value=0)
    trend_data = trend_data.div(trend_data.sum(axis=1), axis=0) * 100  # Chuyển sang phần trăm

    # Tạo danh sách nhãn chủ đề
    topics = trend_data.columns.tolist()

    # Tạo dữ liệu JSON
    data = []
    for (y, m, d), row in trend_data.iterrows():
        date_str = f"{int(d):02d}"
        full_date = datetime(int(y), int(m), int(d)).strftime("%B %d, %Y")
        percentages = {topic: round(float(row[topic]), 1) for topic in topics}
        data.append({
            "date": date_str,
            "fullDate": full_date,
            "percentages": percentages
        })

    return {
        "start_date": start_date,
        "end_date": end_date,
        "topics": topics,
        "data": data,
        "keywords": keywords_data
    }


def get_topic_trends_quarter(quarter: int, year: int, db: Session = Depends(get_db)):
    # Define quarters
    quarters = {
        1: (datetime(year, 1, 1), datetime(year, 3, 31)),  # Q1: Jan-Mar
        2: (datetime(year, 4, 1), datetime(year, 6, 30)),  # Q2: Apr-Jun
        3: (datetime(year, 7, 1), datetime(year, 9, 30)),  # Q3: Jul-Sep
        4: (datetime(year, 10, 1), datetime(year, 12, 31)) # Q4: Oct-Dec
    }

    if quarter not in quarters:
        raise ValueError("Quarter must be 1, 2, 3, or 4")
    
    quarter_start, quarter_end = quarters[quarter]
    quarter_start_str = quarter_start.strftime("%Y-%m-%d")
    quarter_end_str = quarter_end.strftime("%Y-%m-%d")

    # Kết nối cơ sở dữ liệu và lấy dữ liệu
    with engine.connect() as conn:
        sql_query = text("""
            SELECT
                p.id, 
                p.source, 
                p.url, 
                p.category, 
                p.keyword, 
                p.time, 
                p.title, 
                p.content, 
                p.tokens, 
                tq.topic_name, 
                tq.topic 
            FROM paper p 
            JOIN topic_quarter tq ON tq.paper_id = p.id
            WHERE CAST(p.time AS TIMESTAMP) BETWEEN :quarter_start AND :quarter_end
        """)
        result = conn.execute(sql_query, {"quarter_start": f"{quarter_start_str} 00:00:00", "quarter_end": f"{quarter_end_str} 23:59:59"})
        df = pd.DataFrame(result.fetchall(), columns=result.keys())
    
    if df.empty:
        return {
            "quarter": quarter,
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
    df['Topic'] = df['topic']
    df['Topic_Name'] = df['topic_name']

    keywords_data = {}
    result = db.execute(
        text("""
            SELECT topic_name, keyword, value, category
            FROM topic_keywords_quarter
            WHERE year = :year AND quarter = :quarter
            ORDER BY topic_name, value DESC
        """),
        {"year": year, "quarter": quarter}
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

    # Phân tích xu hướng theo ngày trong quý
    quarter_data = df[(df['time'] >= quarter_start) & (df['time'] <= quarter_end + pd.Timedelta(days=1) - pd.Timedelta(seconds=1))]
    trend_data = quarter_data.groupby(['year', 'month', 'day', 'Topic_Name']).size().unstack(fill_value=0)
    trend_data = trend_data.div(trend_data.sum(axis=1), axis=0) * 100  # Chuyển sang phần trăm

    # Tạo danh sách nhãn chủ đề
    topics = trend_data.columns.tolist()

    # Tạo dữ liệu JSON
    data = []
    for (y, m, d), row in trend_data.iterrows():
        date_str = f"{int(m):02d}-{int(d):02d}"
        full_date = datetime(int(y), int(m), int(d)).strftime("%B %d, %Y")
        percentages = {topic: round(float(row[topic]), 1) for topic in topics}
        data.append({
            "date": date_str,
            "fullDate": full_date,
            "percentages": percentages
        })

    return {
        "quarter": quarter,
        "year": year,
        "topics": topics,
        "data": data,
        "keywords": keywords_data
    }


def get_topic_trends_year(year: int, db: Session = Depends(get_db)):
    # Define year boundaries
    year_start = datetime(year, 1, 1)
    year_end = datetime(year, 12, 31)
    year_start_str = year_start.strftime("%Y-%m-%d")
    year_end_str = year_end.strftime("%Y-%m-%d")

    # Kết nối cơ sở dữ liệu và lấy dữ liệu
    with engine.connect() as conn:
        sql_query = text("""
            SELECT
                p.id, 
                p.source, 
                p.url, 
                p.category, 
                p.keyword, 
                p.time, 
                p.title, 
                p.content, 
                p.tokens, 
                ty.topic_name, 
                ty.topic 
            FROM paper p 
            JOIN topic_year ty ON ty.paper_id = p.id
            WHERE CAST(p.time AS TIMESTAMP) BETWEEN :year_start AND :year_end
        """)
        result = conn.execute(sql_query, {"year_start": f"{year_start_str} 00:00:00", "year_end": f"{year_end_str} 23:59:59"})
        df = pd.DataFrame(result.fetchall(), columns=result.keys())
    
    if df.empty:
        return {
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
    df['Topic'] = df['topic']
    df['Topic_Name'] = df['topic_name']

    keywords_data = {}
    result = db.execute(
        text("""
            SELECT topic_name, keyword, value, category
            FROM topic_keywords_year
            WHERE year = :year
            ORDER BY topic_name, value DESC
        """),
        {"year": year}
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

    # Phân tích xu hướng theo ngày trong năm
    year_data = df[(df['time'] >= year_start) & (df['time'] <= year_end + pd.Timedelta(days=1) - pd.Timedelta(seconds=1))]
    trend_data = year_data.groupby(['year', 'month', 'day', 'Topic_Name']).size().unstack(fill_value=0)
    trend_data = trend_data.div(trend_data.sum(axis=1), axis=0) * 100  # Chuyển sang phần trăm

    # Tạo danh sách nhãn chủ đề
    topics = trend_data.columns.tolist()

    # Tạo dữ liệu JSON
    data = []
    for (y, m, d), row in trend_data.iterrows():
        date_str = f"{int(m):02d}-{int(d):02d}"
        full_date = datetime(int(y), int(m), int(d)).strftime("%B %d, %Y")
        percentages = {topic: round(float(row[topic]), 1) for topic in topics}
        data.append({
            "date": date_str,
            "fullDate": full_date,
            "percentages": percentages
        })

    return {
        "year": year,
        "topics": topics,
        "data": data,
        "keywords": keywords_data
    }
