from fastapi import FastAPI
from contextlib import asynccontextmanager
from routers import market, chat
from core.redis_client import init_redis, close_redis, get_redis
from core.postgres import init_pg
from core.cassandra import get_session, close_session

import json
from ingestion.discovery import run_discovery_bootstrap

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──
    print("🚀 Connecting to Cassandra...")
    await get_session()
    print("✅ Cassandra connected!")
    
    print("🚀 Connecting to Redis...")
    await init_redis()
    redis = get_redis()
    print("✅ Redis connected!")

    print("🚀 Connecting to PostgreSQL...")
    await init_pg()
    print("✅ PostgreSQL connected!")
    
    print("🌐 Running Discovery Service...")
    market_symbols = await run_discovery_bootstrap()
    await redis.set("market_symbols", json.dumps(market_symbols))
    print("✅ Discovery complete!")
    
    print("🧠 Skipping Vector DB Warmup to prevent startup hang...")
    
    yield
    # ── Shutdown ──
    print("🛑 Closing Cassandra connection...")
    await close_session()
    print("🛑 Closing Redis connection...")
    await close_redis()

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Stock Tracker API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(market.router, prefix="/api/v1/market", tags=["Market"])
app.include_router(market.ws_router, prefix="/ws", tags=["WebSockets"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["Chatbot"])

@app.get("/health")
async def health_check():
    """Kiểm tra backend và DB có sống không"""
    try:
        session = await get_session()
        stmt = await session.create_prepared("SELECT now() FROM system.local")
        await session.execute(stmt.bind())
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "error", "database": str(e)}