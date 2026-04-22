import asyncio
import json
import time
from datetime import datetime, timezone
import websockets
from core.cassandra import get_session
from core.redis_client import init_redis, get_redis

BINANCE_WS_URL = "wss://stream.binance.com:9443/stream"

_prepared_depth_stmt = None
_prepared_kline_stmt = None

async def init_prepared_statements(session):
    global _prepared_depth_stmt, _prepared_kline_stmt
    if not _prepared_depth_stmt:
        _prepared_depth_stmt = await session.create_prepared(
            "INSERT INTO market_data.depth (symbol, date_bucket, timestamp, bids, asks) VALUES (?, ?, ?, ?, ?)"
        )
    if not _prepared_kline_stmt:
        _prepared_kline_stmt = await session.create_prepared(
            "INSERT INTO market_data.klines (symbol, interval, date_bucket, timestamp, open, high, low, close, volume) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )

# K-lines Aggregator Buffer Memory
current_candles = {}

async def flush_kline_to_db(session, kline_data):
    """Lưu nến 1p đã hoàn tất (đóng nến) xuống Cassandra và Bắn lên Redis"""
    try:
        symbol = kline_data['symbol']
        interval = "1m"
        dt = datetime.fromtimestamp(kline_data['start_time']/1000.0, timezone.utc)
        date_bucket = dt.strftime("%Y-%m-%d")
        
        # Chuyển đổi float thành dạng thập phân tiêu chuẩn để tránh Python tự động xuất "3.8e-06"
        def fmt(val):
            return f"{val:.10f}".rstrip('0').rstrip('.') if '.' in f"{val:.10f}" else f"{val:.10f}"
            
        bound = _prepared_kline_stmt.bind()
        bound.bind_list([
            symbol, interval, date_bucket, int(kline_data['start_time']),
            fmt(kline_data['open']), fmt(kline_data['high']), fmt(kline_data['low']), 
            fmt(kline_data['close']), fmt(kline_data['volume'])
        ])
        
        await session.execute(bound)
        
        # Bắn real-time cho Frontend qua Redis Pub/Sub
        try:
            redis_client = get_redis()
            payload = json.dumps({
                "type": "kline",
                "symbol": symbol,
                "interval": interval,
                "timestamp": int(kline_data['start_time']),
                "close": fmt(kline_data['close'])
            })
            await redis_client.publish("live:klines", payload)
        except Exception as redis_e:
            print(f"Lỗi Redis PubSub: {redis_e}")
            
        print(f"📊 [Kline] Đã đóng nến 1m cho {symbol}: Chốt Close={fmt(kline_data['close'])}")
    except Exception as e:
        print(f"Error flushing kline: {e}")

async def process_trade_message(session, data):
    """
    Nhận dữ liệu khớp lệnh (Trade) siêu rời rạc.
    Gom cụm và cộng dồn dữ liệu Open, High, Low, Close, VOl vào 1 nến phút trong RAM.
    Tự động Insert thẳng vào Cassandra khi sang một phút mới!
    """
    try:
        symbol = data['s']
        price = float(data['p'])
        qty = float(data['q'])
        trade_time = int(data['T']) # ms
        
        # Mốc thời gian tròn phút để neo dữ liệu
        minute_bucket = (trade_time // 60000) * 60000
        
        if symbol not in current_candles:
            current_candles[symbol] = {
                'symbol': symbol, 'start_time': minute_bucket,
                'open': price, 'high': price, 'low': price, 'close': price, 'volume': qty
            }
        else:
            candle = current_candles[symbol]
            if minute_bucket > candle['start_time']:
                # Dữ liệu thuộc phút mới -> Khóa nến hiện tại và ném xuống DataBase không đợi chặn
                asyncio.create_task(flush_kline_to_db(session, candle.copy()))
                
                # Reset Buffer sang mốc mới
                current_candles[symbol] = {
                    'symbol': symbol, 'start_time': minute_bucket,
                    'open': price, 'high': price, 'low': price, 'close': price, 'volume': qty
                }
            else:
                # Nếu vẫn nằm trong nội phút đó -> Chỉ là giá giật lên xuống
                candle['high'] = max(candle['high'], price)
                candle['low'] = min(candle['low'], price)
                candle['close'] = price
                candle['volume'] += qty
    except Exception as e:
        print(f"Trade process error: {e}")

async def process_depth_message(session, data, metrics):
    """
    Xử lý message sổ lệnh và ghi siêu tốc độ vào Cassandra (max 11k/s load test).
    """
    try:
        symbol = data['s']
        dt_now = datetime.now(timezone.utc)
        date_bucket = dt_now.strftime("%Y-%m-%d")
        
        bids_str = json.dumps(data['b'][:10]) 
        asks_str = json.dumps(data['a'][:10])
        
        bound = _prepared_depth_stmt.bind()
        ts_ms = int(dt_now.timestamp() * 1000)
        bound.bind_list([symbol, date_bucket, ts_ms, bids_str, asks_str])
        
        await session.execute(bound)
        metrics['writes'] += 1
    except Exception as e:
        print(f"Error processing depth: {e}")

async def run_binance_combined_stream(symbols):
    session = await get_session()
    await init_prepared_statements(session)
    
    # Link gộp luồng: Binance cho phép nghe Depth và AggTrade chung một websocket duy nhất
    streams = []
    for s in symbols:
        s_lower = s.lower()
        streams.append(f"{s_lower}@depth@100ms")
        streams.append(f"{s_lower}@aggTrade")
        
    url = BINANCE_WS_URL  # Không nhồi toàn bộ names vào URL để tránh lỗi HTTP 414 URI Too Long
    print(f"🔗 [Binance] Đang kết nối chuẩn bị đăng ký {len(symbols)} mã ({len(streams)} luồng)...")
    
    metrics = {'writes': 0}
    last_print = time.time()
    
    async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
        # Binance cấm gửi quá nhiều streams trong 1 mảng JSON, chia ra mỗi block 50 streams
        chunk_size = 50
        for i in range(0, len(streams), chunk_size):
            chunk = streams[i:i + chunk_size]
            sub_msg = {
                "method": "SUBSCRIBE",
                "params": chunk,
                "id": i + 1
            }
            await ws.send(json.dumps(sub_msg))
            await asyncio.sleep(0.2)  # Delay nhẹ nhàng tránh Binance kick vì spam
            
        print("✅ Đã subscribe trọn bộ thành công xuống luồng Binance. Đang rải đạn...")
        
        while True:
            try:
                msg = await ws.recv()
                raw = json.loads(msg)
                
                # Nếu là message confirm từ lệnh SUBSCRIBE
                if "result" in raw and "id" in raw:
                    continue
                    
                # Khi subscribe combined thì data nằm bên trong dict
                if "data" not in raw:
                    continue
                stream_name = raw["stream"]
                data = raw["data"]
                
                # Phân luồng công việc vào Task rời rạc không block vòng while lớn
                if "@depth" in stream_name:
                    asyncio.create_task(process_depth_message(session, data, metrics))
                elif "@aggTrade" in stream_name:
                    asyncio.create_task(process_trade_message(session, data))
                
                # Cập nhật Terminal Log riêng cho luồng Ghi siêu tốc
                if time.time() - last_print >= 5.0:
                    print(f"🚀 [Speed Test] Depth ghi vào Cassandra: {metrics['writes']} tx trong 5 giây (~{metrics['writes']/5:.1f} tx/s)")
                    metrics['writes'] = 0
                    last_print = time.time()
                    
            except Exception as e:
                print(f"Binance WebSocket error: {e}")
                break

if __name__ == "__main__":
    from ingestion.discovery import run_discovery_bootstrap
    
    async def main():
        await init_redis()
        discovery_data = await run_discovery_bootstrap()
        symbols_for_binance = [item["binance"].upper() for item in discovery_data["priority_list"] + discovery_data["remainder_list"]]
        await run_binance_combined_stream(symbols_for_binance)
        
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("Đã dừng tiến trình!")
