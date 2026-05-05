import asyncio
import json
import time
from datetime import datetime, timezone
import websockets
import httpx
import acsylla
from collections import defaultdict
from core.cassandra import get_session
from core.redis_client import init_redis, get_redis
from core.postgres import get_pg_pool
from ingestion.discovery import run_discovery_bootstrap
from core.config import settings
from core.logger import logger
redis_queue = asyncio.Queue()

async def redis_publisher_worker():
    """
    Worker that consumes messages from the internal queue and publishes them to Redis.
    """
    while True:
        channel, payload = await redis_queue.get()
        try:
            redis_client = get_redis()
            await redis_client.publish(channel, payload)
        except Exception:
            pass 
        finally:
            redis_queue.task_done()

_prepared_depth_stmt = None
_prepared_kline_stmt = None

async def init_prepared_statements(session):
    """
    Initializes prepared statements for Cassandra insertions.
    """
    global _prepared_depth_stmt, _prepared_kline_stmt
    if not _prepared_depth_stmt:
        _prepared_depth_stmt = await session.create_prepared(
            "INSERT INTO market_data.depth (symbol, date_bucket, timestamp, bids, asks) VALUES (?, ?, ?, ?, ?)"
        )
    if not _prepared_kline_stmt:
        _prepared_kline_stmt = await session.create_prepared(
            "INSERT INTO market_data.klines (symbol, interval, date_bucket, timestamp, open, high, low, close, volume) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )

intervals_config = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}
current_candles = {} 
depth_buffer = []
kline_buffer = []

def format_decimal(val: float) -> str:
    """
    Formats a float to a decimal string to avoid scientific notation.
    """
    return f"{val:.10f}".rstrip('0').rstrip('.') if '.' in f"{val:.10f}" else f"{val:.10f}"

async def process_trade_message(symbol: str, data: dict):
    """
    Aggregates trade messages into candles for multiple timeframes.
    """
    try:
        price = float(data['p'])
        qty = float(data['q'])
        trade_time = int(data['T'])
        
        if symbol not in current_candles:
            current_candles[symbol] = {}
            
        for inv_name, inv_sec in intervals_config.items():
            bucket = (trade_time // (inv_sec * 1000)) * (inv_sec * 1000)
            if inv_name not in current_candles[symbol]:
                current_candles[symbol][inv_name] = {
                    'start_time': bucket, 'open': price, 'high': price, 'low': price, 'close': price, 'volume': qty
                }
            else:
                candle = current_candles[symbol][inv_name]
                if bucket > candle['start_time']:
                    bound = _prepared_kline_stmt.bind()
                    dt = datetime.fromtimestamp(candle['start_time']/1000.0, timezone.utc)
                    params = [
                        symbol, inv_name, dt.date(),
                        int(candle['start_time']),
                        format_decimal(candle['open']), format_decimal(candle['high']), format_decimal(candle['low']), 
                        format_decimal(candle['close']), format_decimal(candle['volume'])
                    ]
                    dt_naive = dt.replace(tzinfo=None)
                    bound.bind_list([params[0], params[1], params[2], dt_naive] + params[4:])
                    kline_buffer.append((bound, params))
                    
                    current_candles[symbol][inv_name] = {
                        'start_time': bucket, 'open': price, 'high': price, 'low': price, 'close': price, 'volume': qty
                    }
                else:
                    candle['high'] = max(candle['high'], price)
                    candle['low'] = min(candle['low'], price)
                    candle['close'] = price
                    candle['volume'] += qty
                
        candle_1m = current_candles[symbol]['1m']
        payload = json.dumps({
            "type": "kline",
            "symbol": symbol,
            "interval": "1m",
            "timestamp": int(candle_1m['start_time']),
            "open": format_decimal(candle_1m['open']),
            "high": format_decimal(candle_1m['high']),
            "low": format_decimal(candle_1m['low']),
            "close": format_decimal(candle_1m['close']),
            "volume": format_decimal(candle_1m['volume'])
        })
        redis_queue.put_nowait((f"live:klines:{symbol}", payload))
    except Exception as e:
        logger.error(f"[Ingestion] Trade process error for {symbol}: {e}")

async def process_depth_message(symbol: str, data: dict):
    """
    Buffers orderbook depth messages for periodic flushing.
    """
    try:
        ts = int(data.get('E', time.time() * 1000))
        bids = [f"{format_decimal(float(b[0]))}@{format_decimal(float(b[1]))}" for b in data.get('b', [])]
        asks = [f"{format_decimal(float(a[0]))}@{format_decimal(float(a[1]))}" for a in data.get('a', [])]
        bids_str = ",".join(bids)
        asks_str = ",".join(asks)
        dt_now = datetime.now(timezone.utc)
        dt_ts = datetime.fromtimestamp(ts/1000.0, timezone.utc).replace(tzinfo=None)
        bound = _prepared_depth_stmt.bind()
        params = [symbol, dt_now.date(), ts, bids_str, asks_str]
        bound.bind_list([params[0], params[1], dt_ts, params[3], params[4]])
        depth_buffer.append((bound, params))
    except Exception:
        pass

async def run_startup_backfill(session, symbols):
    """
    Backfills historical klines for multiple timeframes on startup.
    """
    logger.info(f"[Ingestion] Startup: Backfilling klines for {len(symbols)} symbols...")
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
                        dt = datetime.fromtimestamp(ts/1000.0, timezone.utc).replace(tzinfo=None)
                        date_bucket = dt.date()
                        bound = _prepared_kline_stmt.bind()
                        bound.bind_list([
                            symbol, interval, date_bucket, dt,
                            format_decimal(float(k[1])), format_decimal(float(k[2])), 
                            format_decimal(float(k[3])), format_decimal(float(k[4])), 
                            format_decimal(float(k[5]))
                        ])
                        await session.execute(bound)
                except Exception:
                    pass
            await asyncio.sleep(0.1)
    logger.info("[Ingestion] Startup backfill complete.")

async def flush_worker(session, redis_client):
    """
    Periodically flushes buffered klines and depth data to Cassandra and PostgreSQL.
    """
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
            
        grouped = defaultdict(list)
        for stmt, params in current_kline:
            grouped[params[0]].append(stmt)
        for stmt, params in current_depth:
            grouped[params[0]].append(stmt)
            
        batches = []
        for symbol, stmts in grouped.items():
            for i in range(0, len(stmts), 100):
                batch = acsylla.create_batch_unlogged()
                for s in stmts[i:i+100]:
                    batch.add_statement(s)
                batches.append(batch)

        sem = asyncio.Semaphore(1000) 
        async def exec_batch(b):
            async with sem:
                try:
                    await session.execute_batch(b)
                except Exception as e:
                    logger.error(f"[DB] Cassandra Batch Error: {e}")
        
        t0 = time.time()
        await asyncio.gather(*[exec_batch(b) for b in batches])
        t1 = time.time()
        latency_ms = (t1 - t0) * 1000

        pg_latency_ms = 0
        try:
            pool = await get_pg_pool()
            async with pool.acquire() as conn:
                if current_kline:
                    pg_klines = []
                    for b in current_kline:
                        p = list(b[1])
                        p[3] = int(p[3]) 
                        pg_klines.append(p)
                    pg_t0 = time.time()
                    await conn.executemany("INSERT INTO klines (symbol, interval, date_bucket, timestamp, open, high, low, close, volume) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) ON CONFLICT DO NOTHING", pg_klines)
                    pg_t1 = time.time()
                
                if current_depth:
                    pg_depths = []
                    for b in current_depth:
                        p = list(b[1])
                        p[2] = int(p[2])
                        pg_depths.append(p)
                    if 'pg_t0' not in locals():
                        pg_t0 = time.time()
                        await conn.executemany("INSERT INTO orderbooks (symbol, date_bucket, timestamp, bids, asks) VALUES ($1, $2, $3, $4, $5) ON CONFLICT DO NOTHING", pg_depths)
                        pg_t1 = time.time()
                    else:
                        sd = time.time()
                        await conn.executemany("INSERT INTO orderbooks (symbol, date_bucket, timestamp, bids, asks) VALUES ($1, $2, $3, $4, $5) ON CONFLICT DO NOTHING", pg_depths)
                        pg_t1 += (time.time() - sd)
                
            if 'pg_t0' in locals():
                pg_latency_ms = (pg_t1 - pg_t0) * 1000
        except Exception as e:
            logger.error(f"[DB] Postgres Flush error: {e}")
        
        await redis_client.set("global_trade_speed", str(total_kline))
        await redis_client.set("global_depth_speed", str(total_depth))
        await redis_client.set("global_total_speed", str(total_all))
        await redis_client.set("cassandra_avg_latency", f"{latency_ms:.2f}")
        await redis_client.set("postgres_avg_latency", f"{pg_latency_ms:.2f}")
        
        logger.info(f"[Ingestion] Flush: {total_kline} klines, {total_depth} depths. Cassandra: {latency_ms:.2f}ms | Postgres: {pg_latency_ms:.2f}ms")

async def run_binance_combined_stream(symbols):
    """
    Subscribes to Binance WebSocket streams for multiple symbols and handles incoming data.
    """
    session = await get_session()
    await init_prepared_statements(session)
    redis_client = get_redis()
    
    asyncio.create_task(run_startup_backfill(session, symbols))
    asyncio.create_task(flush_worker(session, redis_client))
    
    for _ in range(10):
        asyncio.create_task(redis_publisher_worker())
    
    logger.info(f"[Ingestion] Connecting: Subscribing to {len(symbols)} symbols...")
    
    async with websockets.connect(settings.BINANCE_WS_URL, open_timeout=60, ping_interval=20, ping_timeout=20) as ws:
        chunk_size = 50
        symbol_list = list(symbols)
        
        for i in range(0, len(symbol_list), chunk_size):
            chunk = symbol_list[i:i + chunk_size]
            streams = []
            for s in chunk:
                streams.append(f"{s.lower()}@aggTrade")
                streams.append(f"{s.lower()}@depth20@100ms")
            
            subscribe_msg = {"method": "SUBSCRIBE", "params": streams, "id": i + 1}
            await ws.send(json.dumps(subscribe_msg))
            await asyncio.sleep(0.5)
            
        logger.info("[Ingestion] Connected: Streams subscribed successfully.")
        
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
                symbol = stream_name.split('@')[0].upper()
                
                if "@depth" in stream_name:
                    asyncio.create_task(process_depth_message(symbol, data))
                elif "@aggTrade" in stream_name:
                    asyncio.create_task(process_trade_message(symbol, data))
            except Exception as e:
                logger.error(f"[Ingestion] Binance WebSocket error: {e}")
                break

async def main():
    """
    Main entry point for the ingestion service.
    """
    await init_redis()
    discovery_data = await run_discovery_bootstrap()
    symbols = [item["binance"].upper() for item in discovery_data["priority_list"] + discovery_data["remainder_list"]]
    await run_binance_combined_stream(symbols)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("[Ingestion] Process stopped by user.")
