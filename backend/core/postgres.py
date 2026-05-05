import asyncpg
import asyncio
from core.config import settings

_pool = None

async def init_pg():
    """
    Initializes the PostgreSQL connection pool and creates tables if they don't exist.
    """
    global _pool
    for i in range(5):
        try:
            _pool = await asyncpg.create_pool(settings.PG_URL, min_size=5, max_size=20)
            break
        except Exception as e:
            if i == 4:
                print(f"PostgreSQL init error after 5 retries: {e}")
                return
            await asyncio.sleep(2)
    
    if _pool is None:
        return

    try:
        async with _pool.acquire() as conn:
            try:
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
                print("PostgreSQL initialized successfully.")
            except asyncpg.exceptions.UniqueViolationError:
                print("PostgreSQL tables already being created by another worker.")
            except Exception as e:
                if "duplicate_object" in str(e) or "already exists" in str(e).lower():
                    print("PostgreSQL tables already exist.")
                else:
                    raise e
    except Exception as e:
        print(f"PostgreSQL init error: {e}")

async def get_pg_pool() -> asyncpg.Pool:
    """
    Returns the initialized PostgreSQL pool.
    """
    global _pool
    if _pool is None:
        await init_pg()
    return _pool
