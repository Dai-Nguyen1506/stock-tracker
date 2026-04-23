from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException
import httpx
import json
import asyncio
import time
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
from core.cassandra import get_session
from core.redis_client import get_redis

router = APIRouter()
ws_router = APIRouter()

# ── REST API: Symbols ──
@router.get("/symbols")
async def get_symbols():
    redis = get_redis()
    data = await redis.get("market_symbols")
    if data:
        parsed = json.loads(data)
        return {
            "priority": [item["binance"].upper() for item in parsed.get("priority_list", [])],
            "remainder": [item["binance"].upper() for item in parsed.get("remainder_list", [])]
        }
    return {"priority": [], "remainder": []}

# ── REST API: History K-Lines ──
@router.get("/history")
async def get_history(
    symbol: str = Query(..., description="Mã giao dịch ví dụ BTCUSDT"),
    interval: str = Query("1m", description="Khung thời gian nến"),
    limit: int = Query(500, le=2000, description="Số nến cần lấy"),
    before_ts: int = Query(None, description="Lấy dữ liệu trước mốc timestamp này")
):
    """
    Lấy dữ liệu thuần túy từ Cassandra. Trách nhiệm backfill thuộc về Worker lúc khởi động.
    """
    symbol = symbol.upper()
    session = await get_session()
    
    # Do Cassandra query không dễ phân trang lùi qua date_bucket, ta truy vấn linh động
    query = "SELECT timestamp, open, high, low, close, volume FROM market_data.klines WHERE symbol=%s AND interval=%s"
    params = [symbol, interval]
    if before_ts:
        query += " AND timestamp < %s"
        params.append(before_ts)
        
    query += " ALLOW FILTERING" # Hoặc cần cải tiến data model để query by time range
    
    # Tối ưu: Nếu bảng klines chỉ partition theo date_bucket, query trên sẽ rủi ro performance. 
    # Tạm thời cứ truy vấn theo ALLOW FILTERING với set ngày cụ thể.
    # Để an toàn cho load history:
    dt_now = datetime.fromtimestamp(before_ts / 1000.0, timezone.utc) if before_ts else datetime.now(timezone.utc)
    date_bucket = dt_now.strftime("%Y-%m-%d")
    
    query = "SELECT timestamp, open, high, low, close, volume FROM market_data.klines WHERE symbol=%s AND interval=%s AND date_bucket=%s"
    params = [symbol, interval, date_bucket]
    if before_ts:
        query += " AND timestamp < %s"
        params.append(datetime.fromtimestamp(before_ts / 1000.0, timezone.utc))
        
    query += f" ORDER BY timestamp DESC LIMIT {limit}"
    
    rows = await session.execute(query, params)
    
    results = []
    for r in rows:
        results.append({
            "timestamp": int(r.timestamp.timestamp() * 1000) if isinstance(r.timestamp, datetime) else r.timestamp,
            "open": float(r.open),
            "high": float(r.high),
            "low": float(r.low),
            "close": float(r.close),
            "volume": float(r.volume),
        })
        
    return {"symbol": symbol, "interval": interval, "data": results}

import os

async def fetch_alpaca_news(symbol, limit):
    api_key = os.getenv("ALPACA_API_KEY_ID", "")
    secret_key = os.getenv("ALPACA_API_SECRET_KEY", "")
    url = f"https://data.alpaca.markets/v1beta1/news?symbols={symbol}&limit={limit}"
    headers = {"APCA-API-KEY-ID": api_key, "APCA-API-SECRET-KEY": secret_key}
    async with httpx.AsyncClient() as client:
        try:
            res = await client.get(url, headers=headers)
            res.raise_for_status()
            return res.json().get('news', [])
        except:
            return []

async def backfill_news_to_cassandra(symbol, news_list):
    session = await get_session()
    stmt = await session.create_prepared(
        "INSERT INTO market_data.news (symbol, date_bucket, timestamp, headline, summary, url) VALUES (?, ?, ?, ?, ?, ?)"
    )
    for n in news_list:
        ts = int(datetime.fromisoformat(n['created_at'].replace('Z', '+00:00')).timestamp() * 1000)
        dt = datetime.fromtimestamp(ts/1000.0, timezone.utc)
        date_bucket = dt.strftime("%Y-%m-%d")
        bound = stmt.bind()
        bound.bind_list([symbol, date_bucket, ts, n.get('headline', ''), n.get('summary', ''), n.get('url', '')])
        await session.execute(bound)

# ── REST API: News History ──
@router.get("/news/history")
async def get_news_history(
    symbol: str = Query(..., description="Basesymbol, ví dụ BTC"),
    limit: int = Query(20, le=100),
    before_ts: int = Query(None)
):
    session = await get_session()
    dt_now = datetime.fromtimestamp(before_ts / 1000.0, timezone.utc) if before_ts else datetime.now(timezone.utc)
    date_bucket = dt_now.strftime("%Y-%m-%d")
    
    query = "SELECT timestamp, headline, url FROM market_data.news WHERE symbol=%s AND date_bucket=%s"
    params = [symbol, date_bucket]
    if before_ts:
        query += " AND timestamp < %s"
        params.append(datetime.fromtimestamp(before_ts / 1000.0, timezone.utc))
    query += f" ALLOW FILTERING"
    
    rows = await session.execute(query, params)
    
    results = []
    for r in rows:
        results.append({
            "timestamp": int(r.timestamp.timestamp() * 1000) if isinstance(r.timestamp, datetime) else r.timestamp,
            "headline": r.headline,
            "url": r.url,
            "symbol": symbol
        })
        
    results = sorted(results, key=lambda x: x["timestamp"], reverse=True)[:limit]
    
    # Backfill if empty and no before_ts (means initial load)
    if not results and not before_ts:
        alpaca_news = await fetch_alpaca_news(symbol, limit)
        if alpaca_news:
            asyncio.create_task(backfill_news_to_cassandra(symbol, alpaca_news))
            for n in alpaca_news:
                results.append({
                    "timestamp": int(datetime.fromisoformat(n['created_at'].replace('Z', '+00:00')).timestamp() * 1000),
                    "headline": n.get('headline', ''),
                    "url": n.get('url', ''),
                    "symbol": symbol
                })
                
    return {"data": results}

# ── REST API: Stats ──
@router.get("/stats")
async def get_stats():
    redis = get_redis()
    write_speed = await redis.get("cassandra_write_speed")
    ingest_speed = await redis.get("global_ingest_speed")
    peak_write = await redis.get("cassandra_peak_write")
    return {
        "running": write_speed is not None,
        "write_speed_per_s": int(write_speed) if write_speed else 0,
        "ingest_speed_per_s": int(ingest_speed) if ingest_speed else 0,
        "peak_write_per_s": int(peak_write) if peak_write else 0
    }

class PingTestRequest(BaseModel):
    symbol: str
    interval: str
    limit: int = 100
    start_date: str = None
    end_date: str = None

# ── REST API: Ping Cassandra (Test) ──
@router.post("/test/ping")
async def test_ping(request: PingTestRequest):
    import httpx
    import time
    session = await get_session()
    
    if request.start_date and request.end_date:
        start_ts = int(datetime.strptime(request.start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)
        end_ts = int(datetime.strptime(request.end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)
        
        all_klines = []
        current_start = start_ts
        async with httpx.AsyncClient() as client:
            while current_start < end_ts:
                url = f"https://api.binance.com/api/v3/klines?symbol={request.symbol}&interval={request.interval}&startTime={current_start}&endTime={end_ts}&limit=1000"
                res = await client.get(url)
                if res.status_code != 200:
                    break
                data = res.json()
                if not data:
                    break
                all_klines.extend(data)
                current_start = int(data[-1][0]) + 1
                await asyncio.sleep(0.1)

        stmt = await session.create_prepared("INSERT INTO market_data.klines (symbol, interval, date_bucket, timestamp, open, high, low, close, volume) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)")
        def fmt(val): return f"{float(val):.10f}".rstrip('0').rstrip('.') if '.' in f"{float(val):.10f}" else f"{float(val):.10f}"
        
        t0 = time.time()
        for k in all_klines:
            ts = int(k[0])
            dt = datetime.fromtimestamp(ts/1000.0, timezone.utc)
            bound = stmt.bind()
            bound.bind_list([
                request.symbol, request.interval, dt.strftime("%Y-%m-%d"), ts,
                fmt(k[1]), fmt(k[2]), fmt(k[3]), fmt(k[4]), fmt(k[5])
            ])
            await session.execute(bound)
        t1 = time.time()
        
        return {
            "read_ms": 0,
            "write_ms": int((t1 - t0) * 1000),
            "rows": len(all_klines)
        }
    else:
        # Dummy Ping nếu không truyền Start/End Date
        t0 = time.time()
        stmt = await session.create_prepared("INSERT INTO market_data.news (symbol, date_bucket, timestamp, headline, summary, url) VALUES (?, ?, ?, ?, ?, ?)")
        bound = stmt.bind()
        bound.bind_list(["TEST", "2099-01-01", int(time.time()*1000), "ping test", "", ""])
        await session.execute(bound)
        t1 = time.time()
        
        return {
            "read_ms": 0,
            "write_ms": int((t1 - t0) * 1000),
            "rows": 1
        }


# ── WebSockets: Live Streaming cho Frontend ──
# Dùng Redis Pub/Sub để nhận dữ liệu từ các Worker Ingestion

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

manager = ConnectionManager()

@ws_router.websocket("/live/{symbol}")
async def websocket_endpoint(websocket: WebSocket, symbol: str):
    await manager.connect(websocket)
    redis_client = get_redis()
    pubsub = redis_client.pubsub()
    
    symbol = symbol.upper()
    # Đăng ký phòng riêng cho klines của symbol này, và phòng chung cho news
    await pubsub.subscribe(f"live:klines:{symbol}", "live:news")
    
    async def redis_listener():
        try:
            async for message in pubsub.listen():
                if message['type'] == 'message':
                    # Phát thẳng qua WebSocket cho Client
                    data = message['data']
                    await websocket.send_text(data)
        except Exception as e:
            print(f"Redis listener error: {e}")

    listener_task = asyncio.create_task(redis_listener())

    try:
        while True:
            # Chờ ping từ Frontend để giữ kết nối
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        listener_task.cancel()
        await pubsub.unsubscribe()
        print(f"Frontend disconnected from {symbol}.")
    except Exception as e:
        manager.disconnect(websocket)
        listener_task.cancel()
        await pubsub.unsubscribe()
