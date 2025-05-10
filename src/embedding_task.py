import time
from apscheduler.schedulers.background import BackgroundScheduler
from .rag.rag_chain import embedding_pipeline
import pytz
from apscheduler.triggers.cron import CronTrigger

scheduler = BackgroundScheduler()


def start_scheduler():
    vietnam_timezone = pytz.timezone('Asia/Ho_Chi_Minh')
    scheduler.add_job(
        embedding_pipeline,
        CronTrigger(hour=12, minute=14, timezone=vietnam_timezone),
        id="daily_embedding_task",
        replace_existing=True
        )
    scheduler.start()