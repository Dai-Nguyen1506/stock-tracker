import asyncpg
import asyncio
from core.config import settings

_pool = None

async def init_pg(run_ddl: bool = False):
    """
    Initializes the PostgreSQL connection pool. 
    Optional: runs DDL to create tables if run_ddl is True.
    """
    global _pool
    if _pool is not None:
        return _pool

    for i in range(5):
        try:
            _pool = await asyncpg.create_pool(settings.PG_URL, min_size=5, max_size=20)
            break
        except Exception as e:
            if i == 4:
                print(f"PostgreSQL init error after 5 retries: {e}")
                return None
            await asyncio.sleep(2)
    
    if _pool is not None and run_ddl:
        try:
            async with _pool.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS klines (
                        symbol VARCHAR(20),
                        interval VARCHAR(10),
                        date_bucket DATE,
                        timestamp BIGINT,
                        open VARCHAR(30),
                        high VARCHAR(30),
                        low VARCHAR(30),
                        close VARCHAR(30),
                        volume VARCHAR(30),
                        PRIMARY KEY (symbol, interval, date_bucket, timestamp)
                    );
                    CREATE TABLE IF NOT EXISTS orderbooks (
                        symbol VARCHAR(20),
                        date_bucket DATE,
                        timestamp BIGINT,
                        bids TEXT,
                        asks TEXT,
                        PRIMARY KEY (symbol, date_bucket, timestamp)
                    );
                """)
                print("PostgreSQL schema initialized.")
        except Exception as e:
            if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                print("PostgreSQL tables already exist.")
            else:
                print(f"PostgreSQL DDL error: {e}")
    
    return _pool

async def get_pg_pool() -> asyncpg.Pool:
    """
    Returns the initialized PostgreSQL pool, initializing it if necessary.
    """
    global _pool
    if _pool is None:
        await init_pg(run_ddl=False)
    return _pool
