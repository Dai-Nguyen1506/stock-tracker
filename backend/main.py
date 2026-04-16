from fastapi import FastAPI
from contextlib import asynccontextmanager
from core.cassandra import get_session, close_session
from routers import stocks, crypto

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──
    print("🚀 Connecting to Cassandra...")
    await get_session()
    print("✅ Cassandra connected!")
    yield
    # ── Shutdown ──
    print("🛑 Closing Cassandra connection...")
    await close_session()

app = FastAPI(
    title="Stock Tracker API",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(stocks.router, prefix="/api/v1/stocks", tags=["Stocks"])
app.include_router(crypto.router, prefix="/api/v1/crypto", tags=["Crypto"])

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