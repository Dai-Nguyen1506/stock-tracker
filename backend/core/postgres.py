import asyncpg
import asyncio
from core.config import settings

_pool = None

async def init_pg(run_ddl: bool = False):
    """
    Initializes the PostgreSQL connection pool.
    Schema is handled by docker-entrypoint-initdb.d/init.sql.
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
    
    return _pool

async def get_pg_pool() -> asyncpg.Pool:
    """
    Returns the initialized PostgreSQL pool, initializing it if necessary.
    """
    global _pool
    if _pool is None:
        await init_pg(run_ddl=False)
    return _pool
