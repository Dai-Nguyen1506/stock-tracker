from core.cassandra import get_session
from datetime import datetime, timezone
from core.logger import logger

class KlineRepository:
    """
    Repository for handling Kline data in Cassandra.
    """
    def __init__(self):
        self._prepared_history_stmt = None
        self._prepared_history_before_stmt = None
        self._prepared_insert_stmt = None

    async def _init_statements(self):
        """
        Initializes prepared statements for Cassandra queries.
        """
        session = await get_session()
        if self._prepared_history_stmt is None:
            self._prepared_history_stmt = await session.create_prepared(
                "SELECT timestamp, open, high, low, close, volume FROM market_data.klines WHERE symbol=? AND interval=? AND date_bucket=? ORDER BY timestamp DESC"
            )
            self._prepared_history_before_stmt = await session.create_prepared(
                "SELECT timestamp, open, high, low, close, volume FROM market_data.klines WHERE symbol=? AND interval=? AND date_bucket=? AND timestamp < ? ORDER BY timestamp DESC"
            )
            self._prepared_insert_stmt = await session.create_prepared(
                "INSERT INTO market_data.klines (symbol, interval, date_bucket, timestamp, open, high, low, close, volume) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
            )

    async def get_history_by_bucket(self, symbol: str, interval: str, date_bucket, before_ts: int = None):
        """
        Retrieves klines for a specific date bucket.
        """
        await self._init_statements()
        session = await get_session()
        
        try:
            if before_ts:
                bound = self._prepared_history_before_stmt.bind()
                bound.bind_list([symbol, interval, date_bucket, int(before_ts)])
            else:
                bound = self._prepared_history_stmt.bind()
                bound.bind_list([symbol, interval, date_bucket])
            
            return await session.execute(bound)
        except Exception as e:
            logger.error(f"[DB] Cassandra error for {date_bucket}: {e}")
            return []

    async def insert_kline(self, symbol: str, interval: str, date_bucket, dt_ts: datetime, open: float, high: float, low: float, close: float, volume: float):
        """
        Inserts a single kline into Cassandra.
        """
        await self._init_statements()
        session = await get_session()
        
        try:
            bound = self._prepared_insert_stmt.bind()
            bound.bind_list([
                symbol, interval, date_bucket, dt_ts,
                f"{open:.10f}".rstrip('0').rstrip('.'),
                f"{high:.10f}".rstrip('0').rstrip('.'),
                f"{low:.10f}".rstrip('0').rstrip('.'),
                f"{close:.10f}".rstrip('0').rstrip('.'),
                f"{volume:.10f}".rstrip('0').rstrip('.')
            ])
            await session.execute(bound)
        except Exception as e:
            logger.error(f"[DB] Error inserting kline to Cassandra: {e}")
