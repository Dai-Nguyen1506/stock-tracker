from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException
import httpx
import json
import asyncio
from datetime import datetime, timezone, timedelta
from core.cassandra import get_session
from core.redis_client import get_redis

router = APIRouter()
ws_router = APIRouter()

# ── REST API: Backfill Logic ──

async def fetch_binance_klines(symbol: str, interval: str, limit: int):
    """Gọi Binance API REST để lấy lịch sử nến."""
    url = "https://api.binance.com/api/v3/klines"
    params = {
        "symbol": symbol.upper(),
        "interval": interval,
        "limit": limit
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()

async def backfill_klines_to_cassandra(symbol, interval, binance_klines):
    """Ghi klines nhận từ REST API vào Cassandra."""
    session = await get_session()
    stmt = await session.create_prepared(
        "INSERT INTO market_data.klines (symbol, interval, date_bucket, timestamp, open, high, low, close, volume) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )
    
    def fmt(val):
        v_str = f"{float(val):.10f}"
        return v_str.rstrip('0').rstrip('.') if '.' in v_str else v_str
    
    for k in binance_klines:
        # Binance kline format: [Open time, Open, High, Low, Close, Volume, Close time, ...]
        ts = int(k[0])
        dt = datetime.fromtimestamp(ts/1000.0, timezone.utc)
        date_bucket = dt.strftime("%Y-%m-%d")
        
        bound = stmt.bind()
        bound.bind_list([
            symbol, interval, date_bucket, ts,
            fmt(k[1]), fmt(k[2]), fmt(k[3]), fmt(k[4]), fmt(k[5])
        ])
        await session.execute(bound)

@router.get("/history")
async def get_history(
    symbol: str = Query(..., description="Mã giao dịch ví dụ BTCUSDT"),
    interval: str = Query("1m", description="Khung thời gian nến"),
    limit: int = Query(100, le=1000, description="Số nến cần lấy")
):
    """
    Cơ chế Check-first: Lấy K-Lines.
    1. Check Cassandra trong ngày hôm nay.
    2. Nếu thiếu dữ liệu (ví dụ server mới bật) -> Gọi API Binance Backfill -> Trả cho Client.
    """
    symbol = symbol.upper()
    session = await get_session()
    
    dt_now = datetime.now(timezone.utc)
    date_bucket = dt_now.strftime("%Y-%m-%d")
    
    # Query Cassandra
    query = "SELECT timestamp, open, high, low, close, volume FROM market_data.klines WHERE symbol=%s AND interval=%s AND date_bucket=%s ORDER BY timestamp DESC LIMIT %s"
    rows = await session.execute(query, (symbol, interval, date_bucket, limit))
    
    results = []
    for r in rows:
        results.append({
            "timestamp": r.timestamp,
            "open": float(r.open),
            "high": float(r.high),
            "low": float(r.low),
            "close": float(r.close),
            "volume": float(r.volume),
            "is_backfilled": False
        })
        
    # Check-first logic
    if len(results) < limit:
        print(f"⚠️ Dữ liệu {symbol} {interval} bị hụt (Có {len(results)}/{limit}). Tự động Backfill từ Binance...")
        try:
            binance_data = await fetch_binance_klines(symbol, interval, limit)
            # Lọc bỏ những nến đã có để khỏi save đè nếu muốn, nhưng ở đây insert đè (upsert) là an toàn nhất với Cassandra.
            # Ghi đè vào background
            asyncio.create_task(backfill_klines_to_cassandra(symbol, interval, binance_data))
            
            # Re-map kết quả Binance để gửi thẳng lại Frontend cho nhanh (không cần chờ DB select lại)
            binance_results = []
            for k in reversed(binance_data):
                binance_results.append({
                    "timestamp": k[0],
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "volume": float(k[5]),
                    "is_backfilled": True
                })
            return {"symbol": symbol, "interval": interval, "data": binance_results}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Lỗi backfill: {e}")
    else:
        print(f"✅ Lấy dữ liệu {symbol} {interval} trực tiếp từ Cassandra rất mượt!")
        return {"symbol": symbol, "interval": interval, "data": results}


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

@ws_router.websocket("/live")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    redis_client = get_redis()
    pubsub = redis_client.pubsub()
    
    # Đăng ký các kênh phát sóng từ Ingestion (binance_ws.py, alpaca_ws.py)
    await pubsub.subscribe("live:klines", "live:news")
    
    async def redis_listener():
        try:
            async for message in pubsub.listen():
                if message['type'] == 'message':
                    # Phát thẳng qua WebSocket cho toàn bộ Clients
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
        print("Frontend disconnected.")
    except Exception as e:
        manager.disconnect(websocket)
        listener_task.cancel()
        await pubsub.unsubscribe()
