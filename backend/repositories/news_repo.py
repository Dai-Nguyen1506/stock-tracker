from core.cassandra import get_session
from datetime import datetime
from core.logger import logger

class NewsRepository:
    """
    Repository for handling news data in Cassandra.
    """
    def __init__(self):
        self._prepared_news_history_stmt = None
        self._prepared_news_history_before_stmt = None
        self._prepared_insert_stmt = None

    async def _init_statements(self):
        """
        Initializes prepared statements for news queries.
        """
        session = await get_session()
        if self._prepared_news_history_stmt is None:
            self._prepared_news_history_stmt = await session.create_prepared(
                "SELECT timestamp, headline, url FROM market_data.news WHERE symbol=? AND date_bucket=? ORDER BY timestamp DESC"
            )
            self._prepared_news_history_before_stmt = await session.create_prepared(
                "SELECT timestamp, headline, url FROM market_data.news WHERE symbol=? AND date_bucket=? AND timestamp < ? ORDER BY timestamp DESC"
            )
            self._prepared_insert_stmt = await session.create_prepared(
                "INSERT INTO market_data.news (symbol, date_bucket, timestamp, headline, summary, url, sentiment) VALUES (?, ?, ?, ?, ?, ?, ?)"
            )

    async def get_news_by_bucket(self, symbol: str, date_bucket, before_ts: int = None):
        """
        Retrieves news items for a specific date bucket.
        """
        await self._init_statements()
        session = await get_session()
        
        try:
            if before_ts:
                bound = self._prepared_news_history_before_stmt.bind()
                bound.bind_list([symbol, date_bucket, int(before_ts)])
            else:
                bound = self._prepared_news_history_stmt.bind()
                bound.bind_list([symbol, date_bucket])
            
            return await session.execute(bound)
        except Exception as e:
            logger.error(f"[DB] Cassandra error for {date_bucket}: {e}")
            return []

    async def insert_news(self, symbol: str, date_bucket, dt_ts: datetime, headline: str, summary: str, url: str, sentiment: str = "Neutral"):
        """
        Inserts a single news item into Cassandra.
        """
        await self._init_statements()
        session = await get_session()
        
        try:
            bound = self._prepared_insert_stmt.bind()
            bound.bind_list([symbol, date_bucket, dt_ts, headline, summary, url, sentiment])
            await session.execute(bound)
        except Exception as e:
            logger.error(f"[DB] Error inserting news to Cassandra: {e}")
