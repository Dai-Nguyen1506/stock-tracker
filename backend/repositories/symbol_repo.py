import json
from core.redis_client import get_redis
from core.logger import logger

class SymbolRepository:
    """
    Repository for handling symbol and market statistics in Redis.
    """
    async def get_symbols(self) -> dict:
        """
        Retrieves the list of market symbols from Redis.
        """
        redis = get_redis()
        try:
            data = await redis.get("market_symbols")
            if data:
                return json.loads(data)
        except Exception as e:
            logger.error(f"[DB] Error fetching symbols from Redis: {e}")
        return {}
        
    async def get_stats(self) -> dict:
        """
        Retrieves global market data ingestion statistics from Redis.
        """
        redis = get_redis()
        try:
            trade_speed = await redis.get("global_trade_speed")
            depth_speed = await redis.get("global_depth_speed")
            total_speed = await redis.get("global_total_speed")
            latency = await redis.get("cassandra_avg_latency")
            pg_latency = await redis.get("postgres_avg_latency")
            
            return {
                "running": trade_speed is not None,
                "trade_speed": int(trade_speed) if trade_speed else 0,
                "depth_speed": int(depth_speed) if depth_speed else 0,
                "total_speed": int(total_speed) if total_speed else 0,
                "cassandra_latency_ms": float(latency) if latency else 0,
                "postgres_latency_ms": float(pg_latency) if pg_latency else 0
            }
        except Exception as e:
            logger.error(f"[DB] Error fetching stats from Redis: {e}")
            return None
