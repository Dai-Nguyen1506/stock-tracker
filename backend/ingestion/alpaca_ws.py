import asyncio
import json
import logging
from datetime import datetime, timezone
import websockets
from core.cassandra import get_session

ALPACA_WS_URL = "wss://stream.data.alpaca.markets/v1beta1/news"
_prepared_news_stmt = None

async def init_prepared_statements(session):
    global _prepared_news_stmt
    if not _prepared_news_stmt:
        _prepared_news_stmt = await session.create_prepared(
            "INSERT INTO market_data.news (symbol, date_bucket, timestamp, headline, summary, url, sentiment) VALUES (?, ?, ?, ?, ?, ?, ?)"
        )

async def push_to_ai_vector_embedder(symbol, headline, summary):
    pass

async def process_news_message(session, message_list):
    try:
        dt_now = datetime.now(timezone.utc)
        date_bucket = dt_now.strftime("%Y-%m-%d")
        
        for msg in message_list:
            if msg.get('T') != 'n':
                continue
                
            headline = msg.get('headline', '')
            summary = msg.get('summary', '')
            url = msg.get('url', '')
            symbols = msg.get('symbols', [])
            sentiment = "Neutral"

            for symbol in symbols:
                bound = _prepared_news_stmt.bind()
                ts_ms = int(dt_now.timestamp() * 1000)
                bound.bind_list([symbol, date_bucket, ts_ms, headline, summary, url, sentiment])
                
                await session.execute(bound)
                print(f"📰 Bắt được tin tức: {symbol} - {headline}")
                
                asyncio.create_task(push_to_ai_vector_embedder(symbol, headline, summary))
                
    except Exception as e:
        print(f"Error processing news: {e}")

async def run_news_stream(api_key, secret_key, symbols=["*"]):
    if not api_key or not secret_key:
        print("Cảnh báo: Chưa có API Key Alpaca. Xin mời cung cấp trong file .env.")
        return

    session = await get_session()
    await init_prepared_statements(session)
    print(f"📰 [News] Đang kết nối tới Alpaca News WS - Lắng nghe {len(symbols)} mã...")
    
    # Websockets handles standard ping/pong automatically. 
    # Nhưng Alpaca cần chứng thực ngay khi kết nối.
    async with websockets.connect(ALPACA_WS_URL, ping_interval=20, ping_timeout=20) as ws:
        # 1. Gửi Authentication
        await ws.send(json.dumps({"action": "auth", "key": api_key, "secret": secret_key}))
        auth_response = await ws.recv()
        print(f"Auth Response: {auth_response}")
        
        # 2. Đăng ký nhận News theo list Symbol
        await ws.send(json.dumps({"action": "subscribe", "news": symbols}))
        sub_response = await ws.recv()
        print(f"Subscribe Response: {sub_response}")
        
        # 3. Lắng nghe
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

if __name__ == "__main__":
    import os
    from ingestion.discovery import run_discovery_bootstrap
    
    API_KEY = os.getenv("ALPACA_API_KEY_ID", "")
    SECRET_KEY = os.getenv("ALPACA_API_SECRET_KEY", "")
    
    loop = asyncio.get_event_loop()
    
    # Chạy Discovery để lấy mảng priority (Crypto có ở cả Binance và Alpaca)
    # Theo chuẩn Alpaca News stream, symbol yêu cầu dạng Base (ví dụ: BTC, ETH) chứ không phải dạng Trading pair (BTC/USD)
    discovery_data = loop.run_until_complete(run_discovery_bootstrap())
    alpaca_crypto_symbols = [item["base"] for item in discovery_data["priority_list"]]
    
    # Thêm một vài mã chứng khoán mỹ cực Hot để dễ dàng test xem Stream có bắt tin nhắn không
    # (vì Crypto rạng sáng có thể ít tin tức)
    hot_stocks_for_test = ["AAPL", "TSLA", "MSFT", "NVDA", "SPY", "AMZN"]
    
    target_symbols = alpaca_crypto_symbols + hot_stocks_for_test
    print(f"🎯 Khởi chạy cùng danh sách: {target_symbols[:10]}... (Tổng: {len(target_symbols)} mã)")
    
    while True:
        try:
            loop.run_until_complete(run_news_stream(API_KEY, SECRET_KEY, target_symbols))
            print("Restarting Alpaca News Stream...")
        except KeyboardInterrupt:
            break
