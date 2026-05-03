import asyncpg
import os
import asyncio

PG_URL = os.getenv("PG_URL", "postgresql://user:password@postgres:5432/market_data")
_pool = None

async def init_pg():
    global _pool
    try:
        _pool = await asyncpg.create_pool(PG_URL, min_size=5, max_size=20)
        async with _pool.acquire() as conn:
            # Sử dụng một khối try-except nhỏ bên trong để bỏ qua lỗi duplicate nếu nhiều worker khởi tạo cùng lúc
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
                print("✅ PostgreSQL initialized successfully!")
            except asyncpg.exceptions.UniqueViolationError:
                # Nếu gặp lỗi này nghĩa là bảng đang được tạo bởi một process khác, có thể bỏ qua
                print("⚠️ PostgreSQL tables already being created by another worker.")
            except Exception as e:
                if "duplicate_object" in str(e) or "already exists" in str(e).lower():
                    print("⚠️ PostgreSQL tables already exist.")
                else:
                    raise e
    except Exception as e:
        print(f"❌ PostgreSQL init error: {e}")

async def get_pg_pool():
    global _pool
    if _pool is None:
        await init_pg()
    return _pool
