import time
import asyncio
from datetime import datetime, timedelta
import acsylla
from core.cassandra import get_session
from core.postgres import get_pg_pool
from core.logger import logger
from repositories.symbol_repo import SymbolRepository

class BenchmarkService:
    """
    Service for performance benchmarking and database statistics.
    """
    def __init__(self):
        """
        Initializes the BenchmarkService with necessary repositories.
        """
        self.symbol_repo = SymbolRepository()

    async def get_stats(self) -> dict:
        """
        Retrieves global system statistics.
        """
        return await self.symbol_repo.get_stats()

    async def cassandra_ping(self, symbol: str, interval: str, start_date: str = None, end_date: str = None) -> dict:
        """
        Measures Cassandra read performance for kline data.
        """
        session = await get_session()
        
        if start_date and end_date:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            
            t0 = time.time()
            async def fetch_day(date_bucket):
                """Helper to fetch a single day bucket from Cassandra."""
                query = "SELECT * FROM market_data.klines WHERE symbol=? AND interval=? AND date_bucket=?"
                stmt = acsylla.create_statement(query, parameters=[symbol, interval, date_bucket])
                stmt.set_page_size(50000)
                count = 0
                has_more = True
                while has_more:
                    result = await session.execute(stmt)
                    for _ in result:
                        count += 1
                    if result.has_more_pages():
                        stmt.set_page_state(result.page_state())
                    else:
                        has_more = False
                return count

            tasks = []
            curr = start_dt
            while curr <= end_dt:
                tasks.append(fetch_day(curr.date()))
                curr += timedelta(days=1)
                
            results = await asyncio.gather(*tasks)
            total_rows = sum(results)
            t1 = time.time()
            
            return {"read_ms": int((t1 - t0) * 1000), "rows": total_rows}
        else:
            t0 = time.time()
            query = "SELECT now() FROM system.local"
            stmt = acsylla.create_statement(query)
            await session.execute(stmt)
            t1 = time.time()
            return {"read_ms": int((t1 - t0) * 1000), "rows": 1}

    async def postgres_copy(self, symbol: str, interval: str, start_date: str = None, end_date: str = None) -> dict:
        """
        Copies kline data from Cassandra to PostgreSQL and measures performance.
        """
        symbol = symbol.upper()
        session = await get_session()
        
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else None
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else None
        
        all_rows = []
        if start_dt and end_dt:
            curr = start_dt
            while curr <= end_dt:
                cql = "SELECT timestamp, open, high, low, close, volume, date_bucket FROM market_data.klines WHERE symbol=? AND interval=? AND date_bucket=?"
                stmt = acsylla.create_statement(cql, parameters=[symbol, interval, curr])
                stmt.set_page_size(50000)
                has_more = True
                while has_more:
                    res = await session.execute(stmt)
                    for r in res:
                        ts = r.timestamp if isinstance(r.timestamp, int) else int(r.timestamp.timestamp() * 1000)
                        all_rows.append((symbol, interval, r.date_bucket, ts, str(r.open), str(r.high), str(r.low), str(r.close), str(r.volume)))
                    if res.has_more_pages():
                        stmt.set_page_state(res.page_state())
                    else:
                        has_more = False
                curr += timedelta(days=1)
        else:
            cql = "SELECT timestamp, open, high, low, close, volume, date_bucket FROM market_data.klines WHERE symbol=? AND interval=? ALLOW FILTERING"
            stmt = acsylla.create_statement(cql, parameters=[symbol, interval])
            stmt.set_page_size(50000)
            has_more = True
            while has_more:
                res = await session.execute(stmt)
                for r in res:
                    ts = r.timestamp if isinstance(r.timestamp, int) else int(r.timestamp.timestamp() * 1000)
                    all_rows.append((symbol, interval, r.date_bucket, ts, str(r.open), str(r.high), str(r.low), str(r.close), str(r.volume)))
                if res.has_more_pages():
                    stmt.set_page_state(res.page_state())
                else:
                    has_more = False

        if not all_rows:
            return {"status": "No Cassandra data found for copying."}

        pool = await get_pg_pool()
        t0 = time.time()
        async with pool.acquire() as conn:
            if start_dt and end_dt:
                await conn.execute("DELETE FROM klines WHERE symbol=$1 AND interval=$2 AND date_bucket >= $3 AND date_bucket <= $4", symbol, interval, start_dt, end_dt)
            else:
                await conn.execute("DELETE FROM klines WHERE symbol=$1 AND interval=$2", symbol, interval)
            
            await conn.executemany(
                "INSERT INTO klines (symbol, interval, date_bucket, timestamp, open, high, low, close, volume) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) ON CONFLICT DO NOTHING", 
                all_rows
            )
        t1 = time.time()
        return {"status": f"Copied {len(all_rows)} rows to Postgres.", "write_ms": int((t1 - t0) * 1000)}

    async def postgres_ping(self, symbol: str, interval: str, start_date: str = None, end_date: str = None) -> dict:
        """
        Measures PostgreSQL read performance for kline data.
        """
        pool = await get_pg_pool()
        t0 = time.time()
        
        query = "SELECT * FROM klines WHERE symbol=$1 AND interval=$2"
        params = [symbol.upper(), interval]
        
        if start_date and end_date:
            s_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
            e_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
            query += " AND date_bucket >= $3 AND date_bucket <= $4"
            params.extend([s_dt, e_dt])
            
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            total_rows = len(rows)
            
        t1 = time.time()
        return {"read_ms": int((t1 - t0) * 1000), "rows": total_rows}
