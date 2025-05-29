from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from ..database import get_db, engine
import pandas as pd
from datetime import datetime, timedelta
from collections import Counter


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


def discover_popular_topics_today():
    # Lấy ngày hiện tại
    yesterday = datetime.now() - timedelta(days=1)
    today = yesterday.strftime("%Y-%m-%d")

    # Kết nối cơ sở dữ liệu và lấy dữ liệu
    with engine.connect() as conn:
        sql_query = text("""
            SELECT
                p.id, 
                p.source,
                p.url,
                p.title,
                p.category, 
                p.keyword, 
                p.time, 
                tp.topic_name, 
                tp.topic 
            FROM paper p 
            JOIN topic_month tp ON tp.paper_id = p.id
            WHERE CAST(p.time AS TIMESTAMP) >= :today_start AND CAST(p.time AS TIMESTAMP) < :today_end
        """)
        result = conn.execute(sql_query, {
            "today_start": f"{today} 00:00:00",
            "today_end": f"{today} 23:59:59"
        })
        df = pd.DataFrame(result.fetchall(), columns=result.keys())
    
    if df.empty:
        return {
            "date": today,
            "results": [],
        }
    
    # Nhóm các chủ đề theo tên và đếm số lượng
    topic_counts = df['topic_name'].value_counts().reset_index()
    topic_counts.columns = ['topic_name', 'count']
    # topics = topic_counts['topic_name'].tolist()
    # counts = topic_counts['count'].tolist()
    # Lấy thông tin chi tiết của tối đa 5 bài báo cho mỗi chủ đề
    data = []
    for topic in topic_counts['topic_name']:
        # Lấy các bài báo thuộc chủ đề này
        topic_papers = df[df['topic_name'] == topic][['source', 'url', 'title']].head(5).to_dict('records')
        data.append({
            "topic_name": topic.replace("_", " "),
            "count": int(topic_counts[topic_counts['topic_name'] == topic]['count'].iloc[0]),
            "papers": topic_papers  # Danh sách các bài báo (tối đa 5)
        })
    return {
        "date": today,
        "results": data
    }


def discover_popular_topics_this_week():
    # Lấy ngày hiện tại và tính toán ngày bắt đầu và kết thúc của tuần
    today = datetime.now() - timedelta(days=7)
    week_start = today - pd.Timedelta(days=today.weekday())  # Thứ Hai
    week_end = week_start + pd.Timedelta(days=6)  # Chủ Nhật

    # Chuyển đổi sang định dạng chuỗi
    start_date = week_start.strftime("%Y-%m-%d")
    end_date = week_end.strftime("%Y-%m-%d")

    # Kết nối cơ sở dữ liệu và lấy dữ liệu
    with engine.connect() as conn:
        sql_query = text("""
            SELECT
                p.id, 
                p.source,
                p.url,
                p.title,
                p.category, 
                p.keyword, 
                p.time, 
                tw.topic_name, 
                tw.topic 
            FROM paper p 
            JOIN topic_week tw ON tw.paper_id = p.id
            WHERE CAST(p.time AS TIMESTAMP) >= :week_start AND CAST(p.time AS TIMESTAMP) <= :week_end
        """)
        result = conn.execute(sql_query, {
            "week_start": f"{start_date} 00:00:00",
            "week_end": f"{end_date} 23:59:59"
        })
        df = pd.DataFrame(result.fetchall(), columns=result.keys())
    
    if df.empty:
        return {
            "start_date": start_date,
            "end_date": end_date,
            "results": [],
        }
    
    # Nhóm các chủ đề theo tên và đếm số lượng
    topic_counts = df['topic_name'].value_counts().reset_index()
    topic_counts.columns = ['topic_name', 'count']
    # topics = topic_counts['topic_name'].tolist()
    # counts = topic_counts['count'].tolist()
    # Lấy thông tin chi tiết của tối đa 5 bài báo cho mỗi chủ đề
    data = []
    for topic in topic_counts['topic_name']:
        # Lấy các bài báo thuộc chủ đề này
        topic_papers = df[df['topic_name'] == topic][['source', 'url', 'title']].head(5).to_dict('records')
        data.append({
            "topic_name": topic.replace("_", " "),
            "count": int(topic_counts[topic_counts['topic_name'] == topic]['count'].iloc[0]),
            "papers": topic_papers  # Danh sách các bài báo (tối đa 5)
        })
    
    return {
        "start_date": start_date,
        "end_date": end_date,
        "results": data
    }


def discover_popular_topics_this_month():
    # Lấy ngày hiện tại và tháng hiện tại
    today = datetime.now()
    month_start = today.replace(day=1)  # Ngày đầu tiên của tháng
    month_end = (month_start + pd.DateOffset(months=1)) - pd.Timedelta(days=1)  # Ngày cuối cùng của tháng

    # Chuyển đổi sang định dạng chuỗi
    start_date = month_start.strftime("%Y-%m-%d")
    end_date = month_end.strftime("%Y-%m-%d")

    # Kết nối cơ sở dữ liệu và lấy dữ liệu
    with engine.connect() as conn:
        sql_query = text("""
            SELECT
                p.id, 
                p.source,
                p.url,
                p.title,
                p.category, 
                p.keyword, 
                p.time, 
                tm.topic_name, 
                tm.topic 
            FROM paper p 
            JOIN topic_month tm ON tm.paper_id = p.id
            WHERE CAST(p.time AS TIMESTAMP) >= :month_start AND CAST(p.time AS TIMESTAMP) <= :month_end
        """)
        result = conn.execute(sql_query, {
            "month_start": f"{start_date} 00:00:00",
            "month_end": f"{end_date} 23:59:59"
        })
        df = pd.DataFrame(result.fetchall(), columns=result.keys())
    
    if df.empty:
        return {
            "start_date": start_date,
            "end_date": end_date,
            "results": [],
        }
    
    # Nhóm các chủ đề theo tên và đếm số lượng
    topic_counts = df['topic_name'].value_counts().reset_index()
    topic_counts.columns = ['topic_name', 'count']
    # topics = topic_counts['topic_name'].tolist()
    # counts = topic_counts['count'].tolist()
    # Lấy thông tin chi tiết của tối đa 5 bài báo cho mỗi chủ đề
    data = []
    for topic in topic_counts['topic_name']:
        # Lấy các bài báo thuộc chủ đề này
        topic_papers = df[df['topic_name'] == topic][['source', 'url', 'title']].head(5).to_dict('records')
        data.append({
            "topic_name": topic.replace("_", " "),
            "count": int(topic_counts[topic_counts['topic_name'] == topic]['count'].iloc[0]),
            "papers": topic_papers  # Danh sách các bài báo (tối đa 5)
        })
    
    return {
        "start_date": start_date,
        "end_date": end_date,
        "results": data
    }


# Hàm để lấy category và keyword phổ biến nhất trong mỗi chủ đề
def analyze_category_keyword(df):
    topic_info = {}
    for topic_idx in df['topic'].unique():
        # Lấy các bài báo thuộc chủ đề hiện tại
        topic_idx = int(topic_idx)
        topic_df = df[df['topic'] == topic_idx]
        
        # Tìm category phổ biến nhất
        category_counts = topic_df['category'].value_counts()
        top_category = category_counts.index[0] if not category_counts.empty else "Unknown"
        
        # Tìm keyword phổ biến nhất
        all_keywords = []
        for keywords in topic_df['keyword']:
            if isinstance(keywords, str):
                all_keywords.extend([kw.strip().lower() for kw in keywords.split(',')])
        keyword_counts = Counter(all_keywords)
        # Lấy top 3 keyword phổ biến
        top_keywords = [kw for kw, count in keyword_counts.most_common(3)]
        
        # Loại bỏ từ khóa trùng với top_category
        top_category_lower = top_category.lower()
        filtered_keywords = [kw for kw in top_keywords if kw.lower() != top_category_lower]
        filtered_keywords = [kw for kw in filtered_keywords if kw.lower() != 'null']
        filtered_keywords = [kw for kw in filtered_keywords if kw.lower() != 'nan']

        topic_info[topic_idx] = {
            'top_category': top_category,
            'top_keywords': filtered_keywords
        }
    
    return topic_info


def discover_hot_keywords():
    # Lấy ngày hiện tại và tháng hiện tại
    today = datetime.now()
    month_start = today.replace(day=1)  # Ngày đầu tiên của tháng
    month_end = (month_start + pd.DateOffset(months=1)) - pd.Timedelta(days=1)  # Ngày cuối cùng của tháng

    # Chuyển đổi sang định dạng chuỗi
    start_date = month_start.strftime("%Y-%m-%d")
    end_date = month_end.strftime("%Y-%m-%d")

    # Kết nối cơ sở dữ liệu và lấy dữ liệu
    with engine.connect() as conn:
        sql_query = text("""
            SELECT
                p.id, 
                p.category, 
                p.keyword, 
                p.time, 
                tm.topic_name, 
                tm.topic 
            FROM paper p 
            JOIN topic_month tm ON tm.paper_id = p.id
            WHERE CAST(p.time AS TIMESTAMP) >= :month_start AND CAST(p.time AS TIMESTAMP) <= :month_end
        """)
        result = conn.execute(sql_query, {
            "month_start": f"{start_date} 00:00:00",
            "month_end": f"{end_date} 23:59:59"
        })
        df = pd.DataFrame(result.fetchall(), columns=result.keys())
    
    if df.empty:
        return {
            "start_date": start_date,
            "end_date": end_date,
            "results": {},
        }
    
    print("helo")
    topic_info = analyze_category_keyword(df)
    print('topic_info:', topic_info)
    return {
        "start_date": start_date,
        "end_date": end_date,
        "results": topic_info
    }
