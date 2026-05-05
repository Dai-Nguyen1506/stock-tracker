import httpx
import asyncio
from datetime import datetime, timezone, timedelta
from repositories.news_repo import NewsRepository
from core.vector_db import push_to_ai_vector_embedder
from core.logger import logger
from core.config import settings

class NewsService:
    """
    Service for handling financial news data and storage.
    """
    def __init__(self):
        self.news_repo = NewsRepository()

    async def get_news_history(self, symbol: str, limit: int, before_ts: int = None) -> list:
        """
        Retrieves news history from Cassandra with a fallback to Alpaca News API.
        """
        try:
            dt_now = datetime.fromtimestamp(before_ts / 1000.0, timezone.utc) if before_ts else datetime.now(timezone.utc)
            
            results = []
            days_back = 0
            max_days = 7
            current_dt = dt_now
            
            while len(results) < limit and days_back < max_days:
                date_bucket = current_dt.date()
                limit_needed = limit - len(results)
                
                rows = await self.news_repo.get_news_by_bucket(symbol, date_bucket, before_ts if days_back == 0 else None)
                
                count = 0
                for r in rows:
                    if count >= limit_needed:
                        break
                    
                    ts_val = 0
                    if isinstance(r.timestamp, datetime):
                        ts_val = int(r.timestamp.timestamp() * 1000)
                    else:
                        ts_val = r.timestamp
                        
                    results.append({
                        "timestamp": ts_val,
                        "headline": r.headline,
                        "url": r.url,
                        "symbol": symbol
                    })
                    count += 1
                    
                current_dt -= timedelta(days=1)
                days_back += 1
                
            results = sorted(results, key=lambda x: x["timestamp"], reverse=True)[:limit]
            
            if not results and not before_ts:
                logger.warning(f"Database empty for {symbol} news. Fetching from Alpaca API.")
                alpaca_news = await self.fetch_alpaca_news(symbol, limit)
                if alpaca_news:
                    asyncio.create_task(self.backfill_news(symbol, alpaca_news))
                    for n in alpaca_news:
                        dt_obj = datetime.fromisoformat(n['created_at'].replace('Z', '+00:00'))
                        results.append({
                            "timestamp": int(dt_obj.timestamp() * 1000),
                            "headline": n.get('headline', ''),
                            "url": n.get('url', ''),
                            "symbol": symbol
                        })
            return results
        except Exception as e:
            logger.error(f"NewsService error: {e}")
            return []

    async def fetch_alpaca_news(self, symbol: str, limit: int) -> list:
        """
        Fetches live news from Alpaca Data API.
        """
        url = f"https://data.alpaca.markets/v1beta1/news?symbols={symbol}&limit={limit}"
        headers = {
            "APCA-API-KEY-ID": settings.ALPACA_API_KEY_ID, 
            "APCA-API-SECRET-KEY": settings.ALPACA_API_SECRET_KEY
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                res = await client.get(url, headers=headers)
                res.raise_for_status()
                return res.json().get('news', [])
            except Exception as e:
                logger.error(f"Alpaca News Fetch Error: {e}")
                return []

    async def backfill_news(self, symbol: str, news_list: list):
        """
        Saves Alpaca news to Cassandra and indexes them in the Vector DB for AI search.
        """
        for n in news_list:
            dt_utc = datetime.fromisoformat(n['created_at'].replace('Z', '+00:00'))
            ts = int(dt_utc.timestamp() * 1000)
            dt_naive = dt_utc.replace(tzinfo=None)
            date_bucket = dt_naive.date()
            
            await self.news_repo.insert_news(symbol, date_bucket.isoformat(), dt_naive, n.get('headline', ''), n.get('summary', ''), n.get('url', ''))
            
            await push_to_ai_vector_embedder(
                symbol, 
                n.get('headline', ''), 
                n.get('summary', ''), 
                n.get('content', ''), 
                n.get('url', ''), 
                ts
            )
