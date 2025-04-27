from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from ..database import get_db, engine
from collections import Counter
import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation
from datetime import datetime


def analyze_category_keyword(df):
    topic_info = {}
    for topic_idx in df['Topic'].unique():
        # Lấy các bài báo thuộc chủ đề hiện tại
        topic_df = df[df['Topic'] == topic_idx]
        
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
        
        topic_info[topic_idx] = {
            'top_category': top_category,
            'top_keywords': top_keywords
        }
    
    return topic_info


def get_topic_trends(month: int, year: int):
    # Kết nối cơ sở dữ liệu và lấy dữ liệu
    with engine.connect() as conn:
        sql_query = text("SELECT * FROM paper WHERE time LIKE :time_pattern")
        result = conn.execute(sql_query, {"time_pattern": f"{year}-{month:02d}%"})
        df = pd.DataFrame(result.fetchall(), columns=result.keys())

    # Xử lý thời gian
    df['time'] = pd.to_datetime(df['time'], format='%Y-%m-%d %H:%M:%S')
    df['year'] = df['time'].dt.year
    df['month'] = df['time'].dt.month
    df['day'] = df['time'].dt.day
    df.loc[df['keyword'].isin(['NaN', 'Null']), 'keyword'] = df['category']

    # Vector hóa văn bản
    vectorizer = CountVectorizer(max_features=2000)
    X = vectorizer.fit_transform(df['tokens'])

    # Mô hình LDA
    num_topics = 10
    lda = LatentDirichletAllocation(n_components=num_topics, random_state=42, learning_method='online')
    lda_output = lda.fit_transform(X)

    # Gán chủ đề
    df['Topic'] = lda_output.argmax(axis=1)

    # Phân tích category và keyword để tạo nhãn chủ đề
    topic_info = analyze_category_keyword(df)
    topic_names_manual = {}
    for topic_idx in topic_info.keys():
        top_category = topic_info[topic_idx]['top_category']
        top_keywords = topic_info[topic_idx]['top_keywords']
        if top_keywords:
            label = f"{top_category.lower()} {'_'.join(top_keywords[:2]).lower()}"
        else:
            label = top_category.lower()
        topic_names_manual[topic_idx] = label.replace(' ', '_')

    df['Topic_Name'] = df['Topic'].map(topic_names_manual)

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
    
    feature_names = vectorizer.get_feature_names_out()
    keywords_data = {}
    for topic_idx, topic in enumerate(lda.components_):
        topic_name = topic_names_manual.get(topic_idx, f"topic_{topic_idx}")
        top_category = topic_info[topic_idx]['top_category'] if topic_idx in topic_info else "Unknown"
        top_words = [
            {"text": feature_names[i], "value": round(topic[i] * 100 / topic.sum(), 1), "category": top_category}
            for i in topic.argsort()[:-11:-1]
        ]
        keywords_data[topic_name] = top_words

    return {
        "month": month,
        "year": year,
        "topics": topics,
        "data": data,
        "keywords": keywords_data
    }
