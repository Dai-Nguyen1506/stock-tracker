import redis.asyncio as redis
from core.config import settings

_redis_pool = None

async def init_redis():
    global _redis_pool
    if not _redis_pool:
        _redis_pool = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=500
        )
    return _redis_pool

async def close_redis():
    global _redis_pool
    if _redis_pool:
        await _redis_pool.close()
        _redis_pool = None

def get_redis() -> redis.Redis:
    if not _redis_pool:
        raise Exception("Redis pool has not been initialized.")
    return _redis_pool
