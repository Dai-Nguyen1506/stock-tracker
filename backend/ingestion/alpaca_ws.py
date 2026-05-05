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

ALPACA_WS_URL = "wss://stream.data.alpaca.markets/v1beta1/news"
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
                    print(f"Redis PubSub error: {e}")
                    
                print(f"News caught: {symbol} - {headline}")
                asyncio.create_task(push_to_ai_vector_embedder(symbol, headline, summary, content, url, ts_ms))
                
    except Exception as e:
        print(f"Error processing news: {e}")

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
        print(f"News Backfill: DB empty. Fetching news from last 7 days ({start_time})...")
        
        chunk_size = 30
        for i in range(0, len(symbols), chunk_size):
            chunk = [s.upper().strip() for s in symbols[i:i+chunk_size] if s]
            if not chunk: continue
            
            syms_str = ",".join(chunk)
            url = f"https://data.alpaca.markets/v1beta1/news?symbols={syms_str}&start={start_time}&limit=50"
            success = await fetch_and_store_news(session, url, headers)
            
            if not success:
                for s in chunk:
                    single_url = f"https://data.alpaca.markets/v1beta1/news?symbols={s}&start={start_time}&limit=20"
                    await fetch_and_store_news(session, single_url, headers)
                    await asyncio.sleep(0.2)
            
            await asyncio.sleep(0.5)
    else:
        print(f"News Backfill: Database contains data. Last entry: {last_ts}. Fetching newer news...")
        start_time = (last_ts + timedelta(seconds=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
        
        chunk_size = 30
        for i in range(0, len(symbols), chunk_size):
            chunk = [s.upper().strip() for s in symbols[i:i+chunk_size] if s]
            if not chunk: continue
            
            syms_str = ",".join(chunk)
            url = f"https://data.alpaca.markets/v1beta1/news?symbols={syms_str}&start={start_time}&limit=50"
            success = await fetch_and_store_news(session, url, headers)
            
            if not success:
                for s in chunk:
                    single_url = f"https://data.alpaca.markets/v1beta1/news?symbols={s}&start={start_time}&limit=20"
                    await fetch_and_store_news(session, single_url, headers)
                    await asyncio.sleep(0.2)

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
                
                print(f"  Fetched {len(news_data)} news items.")
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
                print(f"  Alpaca API Error: {res.status_code} - {res.text}")
                return False
    except Exception as e:
        print(f"  Fetch news error: {e}")
        return False

async def run_news_stream(api_key, secret_key, symbols):
    """
    Main loop for streaming news from Alpaca WebSocket.
    """
    if not api_key or not secret_key:
        print("Warning: Alpaca API keys are missing.")
        return

    session = await get_session()
    await init_prepared_statements(session)
    
    global _allowed_symbols
    _allowed_symbols = set(symbols)
    
    await run_startup_news_backfill(session, symbols, api_key, secret_key)
    
    print(f"News: Connecting to Alpaca News WS for {len(symbols)} symbols...")
    async with websockets.connect(ALPACA_WS_URL, open_timeout=60, ping_interval=20, ping_timeout=20) as ws:
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
                print("Connection lost to Alpaca. Reconnecting...")
                await asyncio.sleep(5)
                break
            except Exception as e:
                print(f"News WebSocket error: {e}")

async def main():
    """
    Main entry point for the news ingestion service.
    """
    await init_redis()
    api_key = settings.ALPACA_API_KEY_ID
    secret_key = settings.ALPACA_API_SECRET_KEY
    
    discovery_data = await run_discovery_bootstrap()
    target_symbols = [item["base"] for item in discovery_data["priority_list"]]
    
    print(f"Starting News Stream for {len(target_symbols)} symbols.")
    
    while True:
        try:
            await run_news_stream(api_key, secret_key, target_symbols)
            await asyncio.sleep(5)
        except Exception as e:
            print(f"News Stream connection lost: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("Process stopped by user.")
