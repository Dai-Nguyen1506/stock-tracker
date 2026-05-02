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
        date_bucket = dt.date()
        
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
        
        try:
            redis_client = get_redis()
            payload = json.dumps({
                "type": "kline",
                "symbol": symbol,
                "interval": interval,
                "timestamp": int(kline_data['start_time']),
                "open": fmt(kline_data['open']),
                "high": fmt(kline_data['high']),
                "low": fmt(kline_data['low']),
                "close": fmt(kline_data['close']),
                "volume": fmt(kline_data['volume'])
            })
            await redis_client.publish(f"live:klines:{symbol}", payload)
        except Exception as redis_e:
            print(f"Lỗi Redis PubSub: {redis_e}")
            
        print(f"📊 [Kline] Đã đóng nến 1m cho {symbol}: Chốt Close={fmt(kline_data['close'])}")
    except Exception as e:
        print(f"Error flushing kline: {e}")

intervals_config = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}
current_candles = {} # symbol -> {interval: candle_data}
depth_buffer = []
kline_buffer = []

async def process_trade_message(data):
    """
    Cộng dồn Trade vào tất cả các khung thời gian.
    Chỉ chốt (đẩy vào buffer) khi qua nến mới.
    """
    try:
        symbol = data['s']
        price = float(data['p'])
        qty = float(data['q'])
        trade_time = int(data['T']) # ms
        
        if symbol not in current_candles:
            current_candles[symbol] = {}
            
        def fmt(val):
            return f"{val:.10f}".rstrip('0').rstrip('.') if '.' in f"{val:.10f}" else f"{val:.10f}"

        for inv_name, inv_sec in intervals_config.items():
            bucket = (trade_time // (inv_sec * 1000)) * (inv_sec * 1000)
            if inv_name not in current_candles[symbol]:
                current_candles[symbol][inv_name] = {
                    'start_time': bucket, 'open': price, 'high': price, 'low': price, 'close': price, 'volume': qty
                }
            else:
                candle = current_candles[symbol][inv_name]
                if bucket > candle['start_time']:
                    # Khóa nến hiện tại và ném xuống Buffer
                    bound = _prepared_kline_stmt.bind()
                    dt = datetime.fromtimestamp(candle['start_time']/1000.0, timezone.utc)
                    params = [
                        symbol, inv_name, dt.date(),
                        int(candle['start_time']),
                        fmt(candle['open']), fmt(candle['high']), fmt(candle['low']), 
                        fmt(candle['close']), fmt(candle['volume'])
                    ]
                    bound.bind_list(params)
                    kline_buffer.append((bound, params))
                    
                    # Reset Buffer sang mốc mới
                    current_candles[symbol][inv_name] = {
                        'start_time': bucket, 'open': price, 'high': price, 'low': price, 'close': price, 'volume': qty
                    }
                else:
                    # Nằm trong nội phút -> Chỉ là giá giật lên xuống
                    candle['high'] = max(candle['high'], price)
                    candle['low'] = min(candle['low'], price)
                    candle['close'] = price
                    candle['volume'] += qty
                
        # PHÁT LIVE KLINE 1M LÊN REDIS ĐỂ NẾN NHẢY LIÊN TỤC TRÊN UI
        try:
            candle_1m = current_candles[symbol]['1m']
            redis_client = get_redis()
            payload = json.dumps({
                "type": "kline",
                "symbol": symbol,
                "interval": "1m",
                "timestamp": int(candle_1m['start_time']),
                "open": fmt(candle_1m['open']),
                "high": fmt(candle_1m['high']),
                "low": fmt(candle_1m['low']),
                "close": fmt(candle_1m['close']),
                "volume": fmt(candle_1m['volume'])
            })
            asyncio.create_task(redis_client.publish(f"live:klines:{symbol}", payload))
        except Exception as redis_e:
            pass
    except Exception as e:
        print(f"Trade process error: {e}")

async def process_depth_message(data):
    """
    Đưa message sổ lệnh vào buffer để 1 phút sau ghi siêu tốc độ vào Cassandra.
    """
    try:
        def fmt(val):
            return f"{val:.10f}".rstrip('0').rstrip('.') if '.' in f"{val:.10f}" else f"{val:.10f}"
        
        symbol = data['s']
        ts = int(data['E'])
        bids = []
        asks = []
        for bid in data.get('b', []):
            bids.append(f"{fmt(float(bid[0]))}@{fmt(float(bid[1]))}")
        for ask in data.get('a', []):
            asks.append(f"{fmt(float(ask[0]))}@{fmt(float(ask[1]))}")
            
        bids_str = ",".join(bids)
        asks_str = ",".join(asks)
        
        dt_now = datetime.now(timezone.utc)
        bound = _prepared_depth_stmt.bind()
        params = [symbol, dt_now.date(), ts, bids_str, asks_str]
        bound.bind_list(params)
        depth_buffer.append((bound, params))
    except Exception as e:
        pass

import httpx

async def run_startup_backfill(session, symbols):
    print(f"🔄 Đang tự động backfill nến (1m, 15m, 1h, 4h, 1d) cho {len(symbols)} mã...")
    intervals = ["1m", "15m", "1h", "4h", "1d"]
    async with httpx.AsyncClient(timeout=30.0) as client:
        for symbol in symbols:
            for interval in intervals:
                limit = 1000 if interval == "1m" else 500
                url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
                try:
                    res = await client.get(url, timeout=10)
                    if res.status_code != 200:
                        continue
                    data = res.json()
                    for k in data:
                        ts = int(k[0])
                        dt = datetime.fromtimestamp(ts/1000.0, timezone.utc)
                        date_bucket = dt.date()
                        bound = _prepared_kline_stmt.bind()
                        bound.bind_list([
                            symbol, interval, date_bucket, ts,
                            f"{float(k[1]):.10f}".rstrip('0').rstrip('.'),
                            f"{float(k[2]):.10f}".rstrip('0').rstrip('.'),
                            f"{float(k[3]):.10f}".rstrip('0').rstrip('.'),
                            f"{float(k[4]):.10f}".rstrip('0').rstrip('.'),
                            f"{float(k[5]):.10f}".rstrip('0').rstrip('.')
                        ])
                        await session.execute(bound)
                except Exception:
                    pass
            await asyncio.sleep(0.1)
    print("✅ Backfill startup hoàn tất.")

async def flush_worker(session, redis_client):
    global depth_buffer, kline_buffer
    while True:
        await asyncio.sleep(60.0)
        current_kline = kline_buffer.copy()
        current_depth = depth_buffer.copy()
        kline_buffer.clear()
        depth_buffer.clear()
        
        total_kline = len(current_kline)
        total_depth = len(current_depth)
        total_all = total_kline + total_depth
        if total_all == 0:
            continue
            
        # Tối ưu hóa CPU: Lặp đơn giản và batching siêu tốc (Cassandra C-driver cực nhanh)
        import acsylla
        
        # Sắp xếp current_depth theo symbol để các record cùng symbol đứng cạnh nhau
        # Điều này giúp batching cực nhanh mà không cần defaultdict tốn CPU
        current_depth.sort(key=lambda x: x[1][0])
        
        batches = []
        # Batch klines: Do kline ít (chỉ vài trăm), chạy execute thẳng sẽ nhanh hơn tạo batch
        # nhưng để nhất quán ta batch 100 cái 1 lô unlogged
        for i in range(0, len(current_kline), 100):
            batch = acsylla.create_batch_unlogged()
            for b in current_kline[i:i+100]:
                batch.add_statement(b[0])
            batches.append(batch)
            
        # Batch depths: Đã sort theo symbol nên các record cùng symbol nằm liền nhau.
        # Rất an toàn để batch từng cục 100-200.
        for i in range(0, len(current_depth), 200):
            batch = acsylla.create_batch_unlogged()
            for b in current_depth[i:i+200]:
                batch.add_statement(b[0])
            batches.append(batch)

        sem = asyncio.Semaphore(500)
        async def exec_batch(batch):
            async with sem:
                try:
                    await session.execute(batch)
                except Exception as e:
                    pass
        
        tasks = [exec_batch(b) for b in batches]
        
        # Tính thời gian chỉ lúc thực thi DB (để công bằng với Postgres)
        t0 = time.time()
        await asyncio.gather(*tasks)
        t1 = time.time()
        latency_ms = (t1 - t0) * 1000

        # Postgres write
        pg_latency_ms = 0
        try:
            from core.postgres import get_pg_pool
            pool = await get_pg_pool()
            pg_t0 = time.time()
            async with pool.acquire() as conn:
                if current_kline:
                    await conn.executemany("INSERT INTO klines (symbol, interval, date_bucket, timestamp, open, high, low, close, volume) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) ON CONFLICT DO NOTHING", [b[1] for b in current_kline])
                if current_depth:
                    await conn.executemany("INSERT INTO orderbooks (symbol, date_bucket, timestamp, bids, asks) VALUES ($1, $2, $3, $4, $5) ON CONFLICT DO NOTHING", [b[1] for b in current_depth])
            pg_t1 = time.time()
            pg_latency_ms = (pg_t1 - pg_t0) * 1000
        except Exception as e:
            print(f"Postgres Flush error: {e}")
        
        await redis_client.set("global_trade_speed", total_kline)
        await redis_client.set("global_depth_speed", total_depth)
        await redis_client.set("global_total_speed", total_all)
        await redis_client.set("cassandra_avg_latency", f"{latency_ms:.2f}")
        await redis_client.set("postgres_avg_latency", f"{pg_latency_ms:.2f}")
        
        print(f"🚀 [1 Min Flush] Đã tạo {total_kline} nến (all timeframes), ghi {total_depth} depths. Tổng: {total_all} bản ghi. Cassandra: {latency_ms:.2f}ms | Postgres: {pg_latency_ms:.2f}ms")

async def run_binance_combined_stream(symbols):
    session = await get_session()
    await init_prepared_statements(session)
    redis_client = get_redis()
    
    asyncio.create_task(run_startup_backfill(session, symbols))
    asyncio.create_task(flush_worker(session, redis_client))
    
    streams = []
    for s in symbols:
        s_lower = s.lower()
        streams.append(f"{s_lower}@depth@100ms")
        streams.append(f"{s_lower}@aggTrade")
        
    url = BINANCE_WS_URL
    print(f"🔗 [Binance] Đang kết nối chuẩn bị đăng ký {len(symbols)} mã ({len(streams)} luồng)...")
    
    async with websockets.connect(url, open_timeout=60, ping_interval=20, ping_timeout=20) as ws:
        chunk_size = 50
        for i in range(0, len(streams), chunk_size):
            chunk = streams[i:i + chunk_size]
            sub_msg = {
                "method": "SUBSCRIBE",
                "params": chunk,
                "id": i + 1
            }
            await ws.send(json.dumps(sub_msg))
            await asyncio.sleep(0.2)
            
        print("✅ Đã subscribe trọn bộ thành công xuống luồng Binance. Đang rải đạn và chờ flush mỗi phút...")
        
        while True:
            try:
                msg = await ws.recv()
                raw = json.loads(msg)
                
                if "result" in raw and "id" in raw:
                    continue
                if "data" not in raw:
                    continue
                stream_name = raw["stream"]
                data = raw["data"]
                
                if "@depth" in stream_name:
                    asyncio.create_task(process_depth_message(data))
                elif "@aggTrade" in stream_name:
                    asyncio.create_task(process_trade_message(data))
                    
            except Exception as e:
                print(f"Binance WebSocket error: {e}")
                break

if __name__ == "__main__":
    from core.redis_client import init_redis, get_redis
    from core.postgres import get_pg_pool
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
