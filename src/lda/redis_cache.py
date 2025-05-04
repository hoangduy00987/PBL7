import os
import json
import datetime
import pytz
from redis import Redis

redis_client = Redis(
    host=os.getenv('REDIS_HOST', 'localhost'),
    port=int(os.getenv('REDIS_PORT', 6379)),
    decode_responses=True
)

vn_timezone = pytz.timezone('Asia/Ho_Chi_Minh')

def cache_redis(key: str, value: dict):
    json_value = json.dumps(value)

    now = datetime.datetime.now(vn_timezone)
    tomorrow = now + datetime.timedelta(days=1)
    expire_at_vn = datetime.datetime.combine(tomorrow.date(), datetime.time.min).replace(tzinfo=vn_timezone)

    expire_ts_utc = int(expire_at_vn.astimezone(pytz.utc).timestamp())

    redis_client.set(key, json_value)
    redis_client.expireat(key, expire_ts_utc)

def get_cache(key: str):
    cached = redis_client.get(key)
    return json.loads(cached) if cached else None