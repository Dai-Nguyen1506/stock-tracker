from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException
import httpx
import json
import asyncio
import time
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
from core.cassandra import get_session
from core.redis_client import get_redis
import os

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
    symbol = symbol.upper()
    session = await get_session()
    
    dt_now = datetime.fromtimestamp(before_ts / 1000.0, timezone.utc) if before_ts else datetime.now(timezone.utc)
    
    results = []
    days_back = 0
    max_days = 14 # Tăng lên 14 ngày để tìm dữ liệu cũ hơn trong Cassandra
    current_dt = dt_now
    
    while len(results) < limit and days_back < max_days:
        # acsylla DATE type mong muốn object date hoặc int. Thử dùng .date()
        date_bucket = current_dt.date()
        
        query = "SELECT timestamp, open, high, low, close, volume FROM market_data.klines WHERE symbol=? AND interval=? AND date_bucket=?"
        params = [symbol, interval, date_bucket]
        
        # Sửa lỗi logic: Nếu là ngày đầu tiên (days_back == 0), ta lọc theo before_ts
        # Nhưng nếu before_ts không có, ta lấy thoải mái.
        if days_back == 0 and before_ts:
            query += " AND timestamp < ?"
            params.append(datetime.fromtimestamp(before_ts / 1000.0, timezone.utc))
            
        query += f" ORDER BY timestamp DESC LIMIT {limit - len(results)}"
        
        import acsylla
        statement = acsylla.create_statement(query, parameters=params)
        rows = await session.execute(statement)
        
        for r in rows:
            results.append({
                "timestamp": int(r.timestamp.timestamp() * 1000) if isinstance(r.timestamp, datetime) else r.timestamp,
                "open": float(r.open),
                "high": float(r.high),
                "low": float(r.low),
                "close": float(r.close),
                "volume": float(r.volume),
            })
            
        current_dt -= timedelta(days=1)
        days_back += 1
        
    # --- FALLBACK TO BINANCE API IF INSUFFICIENT DATA IN CASSANDRA ---
    if len(results) < limit:
        needed = limit - len(results)
        # Sử dụng before_ts gốc nếu có, nếu không lấy mốc cuối của results
        effective_before_ts = before_ts
        if not effective_before_ts and results:
            effective_before_ts = results[-1]["timestamp"]
        elif not effective_before_ts:
            # Nếu hoàn toàn không có gì, lấy mốc hiện tại
            effective_before_ts = int(time.time() * 1000)
            
        print(f"⚠️ [History Fallback] Cassandra only has {len(results)}/{limit} for {symbol}. Fetching {needed} more from Binance...")
        try:
            api_data = await fetch_binance_klines(symbol, interval, needed, effective_before_ts)
            if api_data:
                # Gộp dữ liệu (Binance trả về DESC theo hàm của ta)
                # Results đang là DESC, api_data cũng là DESC
                results.extend(api_data)
                # Lưu vào DB để lần sau có (chạy background)
                asyncio.create_task(backfill_klines_to_cassandra(symbol, interval, api_data))
        except Exception as e:
            print(f"❌ [History Fallback] Error: {e}")

    return {"symbol": symbol, "interval": interval, "data": results}

async def fetch_binance_klines(symbol, interval, limit, before_ts=None):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    if before_ts:
        url += f"&endTime={before_ts - 1}" # Trừ 1ms để tránh lấy trùng nến tại mốc before_ts
        
    async with httpx.AsyncClient() as client:
        res = await client.get(url, timeout=10)
        res.raise_for_status()
        data = res.json()
        
        results = []
        for k in data:
            results.append({
                "timestamp": int(k[0]),
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5]),
            })
        # Binance trả về ASC (cũ -> mới), ta cần DESC (mới -> cũ) cho frontend? 
        # Thực tế frontend sorted lại, nhưng để đồng bộ với Cassandra ta cứ giữ nguyên hoặc sort DESC.
        # Cassandra trả về DESC (do ORDER BY timestamp DESC).
        return sorted(results, key=lambda x: x["timestamp"], reverse=True)

async def backfill_klines_to_cassandra(symbol, interval, klines):
    try:
        session = await get_session()
        stmt = await session.create_prepared(
            "INSERT INTO market_data.klines (symbol, interval, date_bucket, timestamp, open, high, low, close, volume) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        for k in klines:
            ts = k["timestamp"]
            dt = datetime.fromtimestamp(ts/1000.0, timezone.utc)
            date_bucket = dt.date()
            
            # Helper format decimal to avoid scientific notation if needed, but float is okay for bind
            bound = stmt.bind()
            bound.bind_list([
                symbol, interval, date_bucket, ts,
                f"{k['open']:.10f}".rstrip('0').rstrip('.'),
                f"{k['high']:.10f}".rstrip('0').rstrip('.'),
                f"{k['low']:.10f}".rstrip('0').rstrip('.'),
                f"{k['close']:.10f}".rstrip('0').rstrip('.'),
                f"{k['volume']:.10f}".rstrip('0').rstrip('.')
            ])
            await session.execute(bound)
        print(f"✅ [Backfill] Đã lưu {len(klines)} nến {symbol} ({interval}) vào Cassandra.")
    except Exception as e:
        print(f"❌ [Backfill] Lỗi ghi Cassandra: {e}")

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
        except Exception as e:
            print(f"Alpaca News Fetch Error: {e}")
            return []

async def backfill_news_to_cassandra(symbol, news_list):
    session = await get_session()
    stmt = await session.create_prepared(
        "INSERT INTO market_data.news (symbol, date_bucket, timestamp, headline, summary, url, sentiment) VALUES (?, ?, ?, ?, ?, ?, ?)"
    )
    for n in news_list:
        ts = int(datetime.fromisoformat(n['created_at'].replace('Z', '+00:00')).timestamp() * 1000)
        dt = datetime.fromtimestamp(ts/1000.0, timezone.utc)
        date_bucket = dt.date()
        bound = stmt.bind()
        bound.bind_list([symbol, date_bucket, dt, n.get('headline', ''), n.get('summary', ''), n.get('url', ''), "Neutral"])
        await session.execute(bound)

# ── REST API: News History ──
@router.get("/news/history")
async def get_news_history(
    symbol: str = Query(..., description="Basesymbol, ví dụ BTC"),
    limit: int = Query(20, le=100),
    before_ts: int = Query(None)
):
    try:
        session = await get_session()
        dt_now = datetime.fromtimestamp(before_ts / 1000.0, timezone.utc) if before_ts else datetime.now(timezone.utc)
        
        results = []
        days_back = 0
        max_days = 7 # Quét 7 ngày gần nhất để tìm tin tức
        current_dt = dt_now
        
        print(f"📡 [News History] Querying for {symbol} (before_ts={before_ts})")
        
        while len(results) < limit and days_back < max_days:
            date_bucket = current_dt.date()
            query = "SELECT timestamp, headline, url FROM market_data.news WHERE symbol=? AND date_bucket=?"
            params = [symbol, date_bucket]
            
            # Chỉ áp dụng before_ts cho ngày đầu tiên của vòng lặp
            if before_ts and days_back == 0:
                query += " AND timestamp < ?"
                params.append(datetime.fromtimestamp(before_ts / 1000.0, timezone.utc))
            
            query += " ALLOW FILTERING"
            
            try:
                import acsylla
                statement = acsylla.create_statement(query, parameters=params)
                rows = await session.execute(statement)
                
                for r in rows:
                    # Acsylla trả về datetime cho TIMESTAMP, ta chuyển sang ms cho Frontend
                    ts_val = 0
                    if isinstance(r.timestamp, datetime):
                        ts_val = int(r.timestamp.timestamp() * 1000)
                    else:
                        ts_val = r.timestamp # Fallback if already int
                        
                    results.append({
                        "timestamp": ts_val,
                        "headline": r.headline,
                        "url": r.url,
                        "symbol": symbol
                    })
            except Exception as e:
                print(f"  ❌ Cassandra error for {date_bucket}: {e}")
                
            current_dt -= timedelta(days=1)
            days_back += 1
            
        # Sắp xếp lại vì lấy từ nhiều ngày
        results = sorted(results, key=lambda x: x["timestamp"], reverse=True)[:limit]
        
        # Nếu DB trống và là request lần đầu (không có before_ts), fetch trực tiếp từ Alpaca
        if not results and not before_ts:
            print(f"  ⚠️ DB empty for {symbol}, falling back to Alpaca API...")
            alpaca_news = await fetch_alpaca_news(symbol, limit)
            if alpaca_news:
                # Lưu vào DB để lần sau có
                asyncio.create_task(backfill_news_to_cassandra(symbol, alpaca_news))
                for n in alpaca_news:
                    created_at = n['created_at']
                    dt_obj = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    results.append({
                        "timestamp": int(dt_obj.timestamp() * 1000),
                        "headline": n.get('headline', ''),
                        "url": n.get('url', ''),
                        "symbol": symbol
                    })
                    
        return {"data": results}
    except Exception as e:
        print(f"🔥 Critical error in get_news_history: {e}")
        import traceback
        traceback.print_exc()
        return {"data": [], "error": str(e)}

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


from typing import Optional

class PingTestRequest(BaseModel):
    symbol: str
    interval: str
    limit: int = 100
    start_date: Optional[str] = None
    end_date: Optional[str] = None

# ── REST API: Ping Cassandra (Test) ──
@router.post("/test/ping")
async def test_ping(request: PingTestRequest):
    """
    Test hiệu năng TRUY XUẤT (READ) từ Cassandra.
    """
    try:
        import time
        from datetime import datetime, timezone, timedelta
        import acsylla
        session = await get_session()
        
        if request.start_date and request.end_date:
            start_dt = datetime.strptime(request.start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(request.end_date, "%Y-%m-%d")
            
            total_rows = 0
            t0 = time.time()
            
            # Quét qua từng ngày trong khoảng để lấy dữ liệu (vì partition key chứa date_bucket)
            curr = start_dt
            while curr <= end_dt:
                date_bucket = curr.date()
                query = "SELECT COUNT(*) FROM market_data.klines WHERE symbol=? AND interval=? AND date_bucket=?"
                stmt = acsylla.create_statement(query, parameters=[request.symbol, request.interval, date_bucket])
                result = await session.execute(stmt)
                row = next(iter(result))
                # acsylla returns count as column 0
                total_rows += row[0]
                curr += timedelta(days=1)
                
            t1 = time.time()
            
            return {
                "read_ms": int((t1 - t0) * 1000),
                "write_ms": 0,
                "rows": total_rows
            }
        else:
            # Dummy Read test
            t0 = time.time()
            query = "SELECT now() FROM system.local"
            stmt = acsylla.create_statement(query)
            await session.execute(stmt)
            t1 = time.time()
            return {"read_ms": int((t1 - t0) * 1000), "write_ms": 0, "rows": 1}
            
    except Exception as e:
        import traceback
        return {"error": str(e), "trace": traceback.format_exc()}




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
async def websocket_global_endpoint(websocket: WebSocket):
    """
    Kênh live chung cho News và Global Stats (không lọc theo symbol cụ thể)
    """
    await manager.connect(websocket)
    redis_client = get_redis()
    pubsub = redis_client.pubsub()
    
    # Chỉ đăng ký news và có thể là stats chung
    await pubsub.subscribe("live:news", "live:stats")
    
    async def redis_listener():
        try:
            async for message in pubsub.listen():
                if message['type'] == 'message':
                    await websocket.send_text(message['data'])
        except Exception as e:
            print(f"Global Redis listener error: {e}")

    listener_task = asyncio.create_task(redis_listener())

    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        listener_task.cancel()
        await pubsub.unsubscribe()
    except Exception:
        manager.disconnect(websocket)
        listener_task.cancel()
        await pubsub.unsubscribe()

@ws_router.websocket("/live/{symbol}")
async def websocket_endpoint(websocket: WebSocket, symbol: str):
    await manager.connect(websocket)
    redis_client = get_redis()
    pubsub = redis_client.pubsub()
    
    symbol = symbol.upper()
    await pubsub.subscribe(f"live:klines:{symbol}", "live:news")
    
    async def redis_listener():
        try:
            async for message in pubsub.listen():
                if message['type'] == 'message':
                    await websocket.send_text(message['data'])
        except Exception as e:
            print(f"Redis listener error: {e}")

    listener_task = asyncio.create_task(redis_listener())

    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        listener_task.cancel()
        await pubsub.unsubscribe()
    except Exception:
        manager.disconnect(websocket)
        listener_task.cancel()
        await pubsub.unsubscribe()
