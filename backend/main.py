import json
from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from routers import market, chat, news, benchmark, websockets
from core.redis_client import init_redis, close_redis, get_redis
from core.postgres import init_pg
from core.cassandra import get_session, close_session
from core.logger import logger
from core.exceptions import register_exception_handlers
from ingestion.discovery import run_discovery_bootstrap

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles application startup and shutdown events.
    """
    logger.info("[DB] Connecting to Cassandra...")
    await get_session()
    logger.info("[DB] Cassandra connected.")
    
    logger.info("[DB] Connecting to Redis...")
    await init_redis()
    redis = get_redis()
    logger.info("[DB] Redis connected.")

    logger.info("[DB] Connecting to PostgreSQL...")
    await init_pg()
    logger.info("[DB] PostgreSQL connected.")
    
    logger.info("[App] Running Discovery Service...")
    market_symbols = await run_discovery_bootstrap()
    await redis.set("market_symbols", json.dumps(market_symbols))
    logger.info("[App] Discovery complete.")
    
    yield

    logger.info("[DB] Closing Cassandra connection...")
    await close_session()
    logger.info("[DB] Closing Redis connection...")
    await close_redis()

app = FastAPI(
    title="Stock Tracker API",
    version="0.1.0",
    lifespan=lifespan,
)

register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(market.router, prefix="/api/v1/market", tags=["Market"])
app.include_router(news.router, prefix="/api/v1/market/news", tags=["News"])
app.include_router(benchmark.router, prefix="/api/v1/market", tags=["Benchmark"])
app.include_router(websockets.router, prefix="/ws", tags=["WebSockets"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["Chatbot"])

@app.get("/health")
async def health_check():
    """
    Health check endpoint to verify backend and database status.
    """
    try:
        session = await get_session()
        stmt = await session.create_prepared("SELECT now() FROM system.local")
        await session.execute(stmt.bind())
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "error", "database": str(e)}