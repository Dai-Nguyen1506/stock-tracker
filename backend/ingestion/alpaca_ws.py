import asyncio
import json
import logging
import os
from datetime import datetime, timezone, timedelta
import websockets
import httpx
import acsylla
from core.cassandra import get_session
from core.redis_client import init_redis, get_redis
from core.vector_db import get_news_collection
from ingestion.discovery import run_discovery_bootstrap

ALPACA_WS_URL = "wss://stream.data.alpaca.markets/v1beta1/news"
_prepared_news_stmt = None

async def init_prepared_statements(session):
    global _prepared_news_stmt
    if not _prepared_news_stmt:
        _prepared_news_stmt = await session.create_prepared(
            "INSERT INTO market_data.news (symbol, date_bucket, timestamp, headline, summary, url, sentiment) VALUES (?, ?, ?, ?, ?, ?, ?)"
        )

async def push_to_ai_vector_embedder(symbol, headline, summary, content, url, ts_ms):
    collection = get_news_collection()
    if not collection:
        return
        
    doc_id = f"{symbol}_{ts_ms}"
    text = f"HEADLINE: {headline}\nSUMMARY: {summary}\nCONTENT: {content}"
    
    try:
        # ChromaDB default embedding function will embed the documents automatically
        collection.upsert(
            documents=[text],
            metadatas=[{"symbol": symbol, "url": url, "timestamp": ts_ms, "headline": headline}],
            ids=[doc_id]
        )
        print(f"🧠 Embedded news to ChromaDB for {symbol}")
    except Exception as e:
        print(f"❌ ChromaDB embed error: {e}")

async def process_news_message(session, message_list):
    try:
        dt_now = datetime.now(timezone.utc)
        date_bucket = dt_now.date()
        
        for msg in message_list:
            if msg.get('T') != 'n':
                continue
                
            headline = msg.get('headline', '')
            summary = msg.get('summary', '')
            content = msg.get('content', '') # Có content từ Alpaca WS
            url = msg.get('url', '')
            symbols = msg.get('symbols', [])
            sentiment = "Neutral"

            for symbol in symbols:
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
                    print(f"Lỗi Redis PubSub: {e}")
                    
                print(f"📰 Bắt được tin tức: {symbol} - {headline}")
                asyncio.create_task(push_to_ai_vector_embedder(symbol, headline, summary, content, url, ts_ms))
                
    except Exception as e:
        print(f"Error processing news: {e}")

async def get_last_news_timestamp(session):
    """Lấy timestamp của tin tức mới nhất trong database (toàn bộ các mã)"""
    # Vì bảng news partition theo (symbol, date_bucket), ta không thể query global đơn giản
    # Ta sẽ check ngày hôm nay và ngày hôm qua cho một vài symbol phổ biến để ước lượng
    check_symbols = ["BTC", "ETH", "AAPL", "TSLA"]
    latest_ts = None
    
    dt_now = datetime.now(timezone.utc)
    for i in range(2): # Check hôm nay và hôm qua
        d = (dt_now - timedelta(days=i)).date()
        for s in check_symbols:
            try:
                query = f"SELECT timestamp FROM market_data.news WHERE symbol='{s}' AND date_bucket='{d}' LIMIT 1"
                rows = await session.execute(query)
                for r in rows:
                    ts = r.timestamp
                    if latest_ts is None or ts > latest_ts:
                        latest_ts = ts
            except:
                continue
    return latest_ts

async def run_startup_news_backfill(session, symbols, api_key, secret_key):
    """
    Truy xuất tin tức từ Alpaca:
    1. Nếu DB trống: Lấy 10 bài mới nhất (không quan tâm start time).
    2. Nếu đã có tin: Lấy tin từ mốc mới nhất đến hiện tại.
    """
    if not api_key or not secret_key:
        return

    # Kiểm tra tin tức mới nhất trong DB
    last_ts = await get_last_news_timestamp(session)
    
    headers = {"APCA-API-KEY-ID": api_key, "APCA-API-SECRET-KEY": secret_key}
    
    if last_ts is None:
        print("📡 [News Backfill] Database trống. Đang lấy 10 tin tức mới nhất làm vốn...")
        # Lấy tin tức mới nhất của các symbols mục tiêu
        chunk_size = 30
        for i in range(0, min(len(symbols), 60), chunk_size): # Giới hạn 60 mã để init nhanh
            chunk = symbols[i:i+chunk_size]
            syms_str = ",".join(chunk)
            url = f"https://data.alpaca.markets/v1beta1/news?symbols={syms_str}&limit=10"
            await fetch_and_store_news(session, url, headers)
    else:
        print(f"🔄 [News Backfill] Đã có dữ liệu (Last: {last_ts}). Đang lấy tin bù đắp...")
        start_time = (last_ts + timedelta(seconds=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
        
        chunk_size = 30
        for i in range(0, len(symbols), chunk_size):
            chunk = symbols[i:i+chunk_size]
            syms_str = ",".join(chunk)
            url = f"https://data.alpaca.markets/v1beta1/news?symbols={syms_str}&start={start_time}&limit=50"
            await fetch_and_store_news(session, url, headers)
            await asyncio.sleep(0.5)

async def fetch_and_store_news(session, url, headers):
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                news_data = res.json().get('news', [])
                if not news_data:
                    return
                
                print(f"  └─ Đã lấy {len(news_data)} tin tức.")
                for n in news_data:
                    created_at = n['created_at']
                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    ts_ms = int(dt.timestamp() * 1000)
                    
                    for s in n.get('symbols', []):
                        bound = _prepared_news_stmt.bind()
                        headline = n.get('headline', '')
                        summary = n.get('summary', '')
                        content = n.get('content', '')
                        url_news = n.get('url', '')
                        
                        bound.bind_list([s, dt.date(), dt, headline, summary, url_news, "Neutral"])
                        await session.execute(bound)
                        asyncio.create_task(push_to_ai_vector_embedder(s, headline, summary, content, url_news, ts_ms))
            else:
                print(f"  ❌ Lỗi API Alpaca: {res.status_code}")
    except Exception as e:
        print(f"  ❌ Lỗi fetch news: {e}")

async def run_news_stream(api_key, secret_key, symbols=["*"]):
    if not api_key or not secret_key:
        print("Cảnh báo: Chưa có API Key Alpaca. Xin mời cung cấp trong file .env.")
        return

    session = await get_session()
    await init_prepared_statements(session)
    
    # 1. Chạy Backfill trước khi mở WebSocket
    await run_startup_news_backfill(session, symbols, api_key, secret_key)
    
    print(f"📰 [News] Đang kết nối tới Alpaca News WS - Lắng nghe {len(symbols)} mã...")
    async with websockets.connect(ALPACA_WS_URL, ping_interval=20, ping_timeout=20) as ws:
        await ws.send(json.dumps({"action": "auth", "key": api_key, "secret": secret_key}))
        auth_response = await ws.recv()
        print(f"Auth Response: {auth_response}")
        
        await ws.send(json.dumps({"action": "subscribe", "news": symbols}))
        sub_response = await ws.recv()
        print(f"Subscribe Response: {sub_response}")
        
        while True:
            try:
                msg = await ws.recv()
                data = json.loads(msg)
                asyncio.create_task(process_news_message(session, data))
            except websockets.exceptions.ConnectionClosed:
                print("Lỗi: Mất kết nối tới Alpaca! Thử tự động Reconnect...")
                await asyncio.sleep(5)
                break
            except Exception as e:
                print(f"News WebSocket error: {e}")

async def main():
    await init_redis()
    API_KEY = os.getenv("ALPACA_API_KEY_ID", "")
    SECRET_KEY = os.getenv("ALPACA_API_SECRET_KEY", "")
    
    discovery_data = await run_discovery_bootstrap()
    alpaca_crypto_symbols = [item["base"] for item in discovery_data["priority_list"]]
    hot_stocks_for_test = ["AAPL", "TSLA", "MSFT", "NVDA", "SPY", "AMZN"]
    target_symbols = alpaca_crypto_symbols + hot_stocks_for_test
    
    print(f"🎯 Khởi chạy cùng danh sách: {target_symbols[:10]}... (Tổng: {len(target_symbols)} mã)")
    
    while True:
        try:
            await run_news_stream(API_KEY, SECRET_KEY, target_symbols)
            print("Restarting Alpaca News Stream...")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"Mất kết nối: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("\nĐã dừng tiến trình!")
