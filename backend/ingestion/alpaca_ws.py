import asyncio
import json
import os
from datetime import datetime, timezone, timedelta
import websockets
import httpx
from core.cassandra import get_session
from core.redis_client import init_redis, get_redis
from core.vector_db import get_news_collection, push_to_ai_vector_embedder
from ingestion.discovery import run_discovery_bootstrap
from core.config import settings
from core.logger import logger
_prepared_news_stmt = None
_allowed_symbols = set()

async def init_prepared_statements(session):
    """
    Initializes prepared statements for news insertion in Cassandra.
    """
    global _prepared_news_stmt
    if not _prepared_news_stmt:
        _prepared_news_stmt = await session.create_prepared(
            "INSERT INTO market_data.news (symbol, date_bucket, timestamp, headline, summary, url, sentiment) VALUES (?, ?, ?, ?, ?, ?, ?)"
        )

async def process_news_message(session, message_list):
    """
    Processes real-time news messages from Alpaca WebSocket.
    """
    try:
        dt_now = datetime.now(timezone.utc)
        date_bucket = dt_now.date()
        
        for msg in message_list:
            if msg.get('T') != 'n':
                continue
                
            headline = msg.get('headline', '')
            summary = msg.get('summary', '')
            content = msg.get('content', '')
            url = msg.get('url', '')
            symbols = msg.get('symbols', [])
            sentiment = "Neutral"

            for symbol in symbols:
                if symbol not in _allowed_symbols:
                    continue
                    
                ts_ms = int(dt_now.timestamp() * 1000)
                bound = _prepared_news_stmt.bind()
                bound.bind_list([symbol, date_bucket, dt_now, headline, summary, url, sentiment])
                await session.execute(bound)
                
                try:
                    redis_client = get_redis()
                    payload = json.dumps({
                        "type": "news",
                        "symbol": symbol,
                        "headline": headline,
                        "url": url,
                        "timestamp": ts_ms
                    })
                    await redis_client.publish("live:news", payload)
                except Exception as e:
                    logger.error(f"[WS] Redis PubSub error: {e}")
                    
                logger.info(f"[Ingestion] News caught: {symbol} - {headline[:50]}...")
                asyncio.create_task(push_to_ai_vector_embedder(symbol, headline, summary, content, url, ts_ms))
                
    except Exception as e:
        logger.error(f"[Ingestion] News process error: {e}")

async def get_last_news_timestamp(session) -> datetime:
    """
    Retrieves the timestamp of the latest news item in the database for reference symbols.
    """
    check_symbols = ["BTC", "ETH", "AAPL", "TSLA", "MSFT", "NVDA"]
    latest_ts = None
    dt_now = datetime.now(timezone.utc)
    for i in range(7):
        d = (dt_now - timedelta(days=i)).date()
        for s in check_symbols:
            try:
                query = f"SELECT timestamp FROM market_data.news WHERE symbol='{s}' AND date_bucket='{d}' ORDER BY timestamp DESC LIMIT 1"
                rows = await session.execute(query)
                for r in rows:
                    ts = r.timestamp
                    if latest_ts is None or ts > latest_ts:
                        latest_ts = ts
                if latest_ts and i == 0: 
                    return latest_ts
            except:
                continue
    return latest_ts

async def run_startup_news_backfill(session, symbols, api_key, secret_key):
    """
    Backfills missing news items on startup from Alpaca REST API.
    """
    if not api_key or not secret_key:
        return

    last_ts = await get_last_news_timestamp(session)
    headers = {"APCA-API-KEY-ID": api_key, "APCA-API-SECRET-KEY": secret_key}
    
    if last_ts is None:
        start_time_dt = datetime.now(timezone.utc) - timedelta(days=7)
        start_time = start_time_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        logger.info(f"[Ingestion] News Backfill: DB empty. Fetching news from last 7 days...")
        
        chunk_size = 30
        for i in range(0, len(symbols), chunk_size):
            chunk = [s.upper().strip() for s in symbols[i:i+chunk_size] if s]
            if not chunk: continue
            syms_str = ",".join(chunk)
            url = f"https://data.alpaca.markets/v1beta1/news?symbols={syms_str}&start={start_time}&limit=50"
            await fetch_and_store_news(session, url, headers)
            await asyncio.sleep(0.5)
    else:
        logger.info(f"[Ingestion] News Backfill: Last entry: {last_ts}. Fetching newer news...")
        start_time = (last_ts + timedelta(seconds=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
        
        chunk_size = 30
        for i in range(0, len(symbols), chunk_size):
            chunk = [s.upper().strip() for s in symbols[i:i+chunk_size] if s]
            if not chunk: continue
            syms_str = ",".join(chunk)
            url = f"https://data.alpaca.markets/v1beta1/news?symbols={syms_str}&start={start_time}&limit=50"
            await fetch_and_store_news(session, url, headers)
            await asyncio.sleep(0.5)

async def fetch_and_store_news(session, url, headers) -> bool:
    """
    Helper function to fetch news from a URL and store it in Cassandra and Vector DB.
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                news_data = res.json().get('news', [])
                if not news_data:
                    return True
                
                logger.info(f"[Ingestion] Backfilled {len(news_data)} news items.")
                for n in news_data:
                    created_at = n['created_at']
                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    ts_ms = int(dt.timestamp() * 1000)
                    for s in n.get('symbols', []):
                        if s not in _allowed_symbols:
                            continue
                        bound = _prepared_news_stmt.bind()
                        headline = n.get('headline', '')
                        summary = n.get('summary', '')
                        content = n.get('content', '')
                        url_news = n.get('url', '')
                        bound.bind_list([s, dt.date(), dt, headline, summary, url_news, "Neutral"])
                        await session.execute(bound)
                        asyncio.create_task(push_to_ai_vector_embedder(s, headline, summary, content, url_news, ts_ms))
                return True
            else:
                logger.error(f"[Alpaca] API Error: {res.status_code}")
                return False
    except Exception as e:
        logger.error(f"[Ingestion] News fetch error: {e}")
        return False

async def run_news_stream(api_key, secret_key, symbols):
    """
    Main loop for streaming news from Alpaca WebSocket.
    """
    if not api_key or not secret_key:
        logger.warning("[Ingestion] Alpaca API keys missing.")
        return

    session = await get_session()
    await init_prepared_statements(session)
    global _allowed_symbols
    _allowed_symbols = set(symbols)
    
    await run_startup_news_backfill(session, symbols, api_key, secret_key)
    
    logger.info(f"[Ingestion] Connecting to Alpaca News WS for {len(symbols)} symbols...")
    async with websockets.connect(settings.ALPACA_WS_URL, open_timeout=60, ping_interval=20, ping_timeout=20) as ws:
        await ws.send(json.dumps({"action": "auth", "key": api_key, "secret": secret_key}))
        await ws.recv()
        await ws.send(json.dumps({"action": "subscribe", "news": symbols}))
        await ws.recv()
        
        while True:
            try:
                msg = await ws.recv()
                data = json.loads(msg)
                asyncio.create_task(process_news_message(session, data))
            except websockets.exceptions.ConnectionClosed:
                logger.warning("[Ingestion] Alpaca connection lost. Reconnecting...")
                await asyncio.sleep(5)
                break
            except Exception as e:
                logger.error(f"[Ingestion] News WebSocket error: {e}")

async def main():
    """
    Main entry point for the news ingestion service.
    """
    await init_redis()
    api_key = settings.ALPACA_API_KEY_ID
    secret_key = settings.ALPACA_API_SECRET_KEY
    discovery_data = await run_discovery_bootstrap()
    target_symbols = [item["base"] for item in discovery_data["priority_list"]]
    
    logger.info(f"[Ingestion] Starting News Stream for {len(target_symbols)} symbols.")
    while True:
        try:
            await run_news_stream(api_key, secret_key, target_symbols)
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"[Ingestion] News Stream crashed: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("[Ingestion] News process stopped by user.")
