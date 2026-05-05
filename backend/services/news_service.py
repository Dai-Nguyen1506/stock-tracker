import httpx
import asyncio
from datetime import datetime, timezone, timedelta
import calendar
from repositories.news_repo import NewsRepository
from core.vector_db import push_to_ai_vector_embedder
from core.logger import logger
from core.config import settings

class NewsService:
    """
    Service for handling financial news data with proactive "Month-Ahead" backfilling logic.
    """
    def __init__(self):
        self.news_repo = NewsRepository()

    async def get_news_history(self, symbol: str, limit: int, before_ts: int = None, year: int = None, month: int = None) -> tuple:
        """
        Retrieves news for a target month.
        If year and month are provided, they take precedence.
        Otherwise, before_ts or current time is used.
        """
        try:
            if year and month:
                target_year = year
                target_month = month
                target_dt = datetime(year, month, 1, tzinfo=timezone.utc)
            elif before_ts:
                target_dt = datetime.fromtimestamp(before_ts / 1000.0, timezone.utc)
                target_year = target_dt.year
                target_month = target_dt.month
            else:
                target_dt = datetime.now(timezone.utc)
                target_year = target_dt.year
                target_month = target_dt.month
            
            results = await self._fetch_month_from_cassandra(symbol, target_year, target_month, before_ts)
            results = sorted(results, key=lambda x: x["timestamp"], reverse=True)[:limit]

            first_day = datetime(target_year, target_month, 1, tzinfo=timezone.utc)
            prev_month_dt = first_day - timedelta(days=1)
            
            asyncio.create_task(self._ensure_month_data(symbol, prev_month_dt.year, prev_month_dt.month))
            
            return results, target_year, target_month
        except Exception as e:
            logger.error(f"[News] History retrieval failed: {e}")
            return [], datetime.now().year, datetime.now().month

    async def _ensure_month_data(self, symbol: str, year: int, month: int):
        """
        Checks if the specified month has data in Cassandra. If not, fetches from Alpaca.
        """
        try:
            check_dates = [
                datetime(year, month, 1).date().isoformat(),
                datetime(year, month, 15).date().isoformat()
            ]
            
            has_data = False
            for d in check_dates:
                rows = await self.news_repo.get_news_by_bucket(symbol, d)
                if any(rows):
                    has_data = True
                    break
            
            if not has_data:
                logger.info(f"[News] Missing data for {year}-{month} ({symbol}). Fetching from Alpaca...")
                start_date = datetime(year, month, 1, tzinfo=timezone.utc)
                last_day = calendar.monthrange(year, month)[1]
                end_date = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc)
                
                api_news = await self.fetch_alpaca_news(symbol, limit=50, start=start_date, end=end_date)
                if api_news:
                    await self.backfill_news(symbol, api_news)
                    logger.info(f"[News] Successfully backfilled {len(api_news)} items for {year}-{month}")
            else:
                logger.debug(f"[News] Month {year}-{month} exists. Triggering VectorDB sync...")
                asyncio.create_task(self._sync_month_to_vector_db(symbol, year, month))
        except Exception as e:
            logger.error(f"[News] Proactive check failed for {year}-{month}: {e}")

    async def _sync_month_to_vector_db(self, symbol: str, year: int, month: int):
        """
        Fetches a month of news from Cassandra and ensures it's indexed in ChromaDB.
        """
        try:
            results = await self._fetch_month_from_cassandra(symbol, year, month)
            if not results:
                return
                
            for item in results:
                await push_to_ai_vector_embedder(
                    symbol=symbol,
                    headline=item['headline'],
                    summary="",
                    content="",
                    url=item['url'],
                    ts_ms=item['timestamp']
                )
            logger.info(f"🔄 [VectorDB] Synced {len(results)} items for {year}-{month} ({symbol})")
        except Exception as e:
            logger.error(f"[VectorDB] Sync failed for {year}-{month}: {e}")

    async def _fetch_month_from_cassandra(self, symbol: str, year: int, month: int, before_ts: int = None) -> list:
        """Retrieves all news for a specific month from Cassandra."""
        results = []
        last_day = calendar.monthrange(year, month)[1]
        
        max_day = last_day
        if before_ts:
            dt_before = datetime.fromtimestamp(before_ts / 1000.0, timezone.utc)
            if dt_before.year == year and dt_before.month == month:
                max_day = dt_before.day

        tasks = []
        for day in range(1, max_day + 1):
            date_bucket = datetime(year, month, day).date().isoformat()
            tasks.append(self.news_repo.get_news_by_bucket(symbol, date_bucket, before_ts))
            
        day_results = await asyncio.gather(*tasks)
        for rows in day_results:
            for r in rows:
                ts_val = int(r.timestamp.timestamp() * 1000) if isinstance(r.timestamp, datetime) else r.timestamp
                results.append({
                    "timestamp": ts_val,
                    "headline": r.headline,
                    "url": r.url,
                    "symbol": symbol
                })
        return results

    def _format_alpaca_news(self, symbol: str, api_news: list) -> list:
        """Formats raw Alpaca news list into our standard format."""
        results = []
        for n in api_news:
            dt_obj = datetime.fromisoformat(n['created_at'].replace('Z', '+00:00'))
            results.append({
                "timestamp": int(dt_obj.timestamp() * 1000),
                "headline": n.get('headline', ''),
                "url": n.get('url', ''),
                "symbol": symbol
            })
        return results

    async def fetch_alpaca_news(self, symbol: str, limit: int = 50, start: datetime = None, end: datetime = None) -> list:
        """
        Fetches news from Alpaca Data API with optional time range.
        """
        safe_limit = min(limit, 50)
        url = f"{settings.ALPACA_DATA_URL}/news?symbols={symbol}&limit={safe_limit}"
        if start:
            url += f"&start={start.strftime('%Y-%m-%dT%H:%M:%SZ')}"
        if end:
            url += f"&end={end.strftime('%Y-%m-%dT%H:%M:%SZ')}"
            
        headers = {
            "APCA-API-KEY-ID": settings.ALPACA_API_KEY_ID, 
            "APCA-API-SECRET-KEY": settings.ALPACA_API_SECRET_KEY
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                res = await client.get(url, headers=headers)
                if res.status_code != 200:
                    logger.error(f"[Alpaca] API Error ({res.status_code}): {res.text}")
                    return []
                return res.json().get('news', [])
            except Exception as e:
                logger.error(f"[Alpaca] Fetch exception: {e}")
                return []

    async def backfill_news(self, symbol: str, news_list: list):
        """
        Saves news to both Cassandra and ChromaDB.
        """
        for n in news_list:
            try:
                dt_utc = datetime.fromisoformat(n['created_at'].replace('Z', '+00:00'))
                ts = int(dt_utc.timestamp() * 1000)
                dt_naive = dt_utc.replace(tzinfo=None)
                date_bucket = dt_naive.date()
                
                await self.news_repo.insert_news(
                    symbol, 
                    date_bucket.isoformat(), 
                    dt_naive, 
                    n.get('headline', ''), 
                    n.get('summary', ''), 
                    n.get('url', '')
                )
                
                asyncio.create_task(push_to_ai_vector_embedder(
                    symbol, 
                    n.get('headline', ''), 
                    n.get('summary', ''), 
                    n.get('content', ''), 
                    n.get('url', ''), 
                    ts
                ))
            except Exception as e:
                logger.error(f"[News] Backfill item failed: {e}")
