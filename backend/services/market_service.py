import httpx
import asyncio
import time
from datetime import datetime, timezone, timedelta
from repositories.kline_repo import KlineRepository
from repositories.symbol_repo import SymbolRepository
from core.logger import logger

class MarketService:
    """
    Service for handling market data, including historical klines and symbol lists.
    """
    def __init__(self):
        self.kline_repo = KlineRepository()
        self.symbol_repo = SymbolRepository()

    async def get_symbols(self) -> dict:
        """
        Retrieves the list of symbols from the repository and formats them.
        """
        data = await self.symbol_repo.get_symbols()
        if not data:
            return {"priority": [], "remainder": []}
        
        return {
            "priority": [item["binance"].upper() for item in data.get("priority_list", [])],
            "remainder": [item["binance"].upper() for item in data.get("remainder_list", [])]
        }

    async def get_history(self, symbol: str, interval: str, limit: int, before_ts: int = None) -> list:
        """
        Retrieves historical kline data from Cassandra, with a fallback to Binance API.
        """
        symbol = symbol.upper()
        
        if before_ts and before_ts > 10**14: 
            before_ts = before_ts // 1000
            
        try:
            dt_now = datetime.fromtimestamp(before_ts / 1000.0, timezone.utc) if before_ts else datetime.now(timezone.utc)
        except (ValueError, OSError, OverflowError):
            dt_now = datetime.now(timezone.utc)
        
        results = []
        days_back = 0
        max_days = 14
        current_dt = dt_now
        
        while len(results) < limit and days_back < max_days:
            date_bucket = current_dt.date()
            limit_needed = limit - len(results)
            
            rows = await self.kline_repo.get_history_by_bucket(symbol, interval, date_bucket, before_ts if days_back == 0 else None)
            
            count = 0
            for r in rows:
                if count >= limit_needed:
                    break
                try:
                    ts_datetime = r.timestamp if isinstance(r.timestamp, datetime) else datetime.fromtimestamp(r.timestamp/1000.0, timezone.utc)
                    if ts_datetime.year > 3000:
                        continue
                    
                    ts_val = int(ts_datetime.timestamp() * 1000)
                    results.append({
                        "timestamp": ts_val,
                        "open": float(r.open),
                        "high": float(r.high),
                        "low": float(r.low),
                        "close": float(r.close),
                        "volume": float(r.volume),
                    })
                    count += 1
                except Exception:
                    continue
            
            current_dt -= timedelta(days=1)
            days_back += 1
            
        final_merged = {x["timestamp"]: x for x in results}
        sorted_results = sorted(final_merged.values(), key=lambda x: x["timestamp"])
        
        if before_ts:
            results = [r for r in sorted_results if r["timestamp"] < int(before_ts)]
        else:
            results = sorted_results
            
        if len(results) < limit:
            needed = limit - len(results)
            effective_before_ts = before_ts
            if not effective_before_ts and results:
                effective_before_ts = results[0]["timestamp"]
            elif not effective_before_ts:
                effective_before_ts = int(time.time() * 1000)
                
            logger.warning(f"History Fallback: Only have {len(results)}/{limit} for {symbol}. Fetching {needed} more from Binance.")
            try:
                api_data = await self.fetch_binance_klines(symbol, interval, needed, effective_before_ts)
                if api_data:
                    merged = {x["timestamp"]: x for x in results}
                    for candle in api_data:
                        if candle["timestamp"] not in merged:
                            merged[candle["timestamp"]] = candle
                    results = sorted(merged.values(), key=lambda x: x["timestamp"])
                    
                    asyncio.create_task(self.backfill_klines(symbol, interval, api_data))
            except Exception as e:
                logger.error(f"History Fallback error: {e}")
                
        return results

    async def fetch_binance_klines(self, symbol: str, interval: str, limit: int, before_ts: int = None) -> list:
        """
        Fetches kline data directly from the Binance REST API.
        """
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
        if before_ts:
            url += f"&endTime={int(before_ts) - 1000}"
            
        async with httpx.AsyncClient(timeout=30.0) as client:
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
            return sorted(results, key=lambda x: x["timestamp"], reverse=True)

    async def backfill_klines(self, symbol: str, interval: str, klines: list):
        """
        Saves klines fetched from external API into the local Cassandra database.
        """
        for k in klines:
            ts = k["timestamp"]
            dt_ts = datetime.fromtimestamp(ts/1000.0, timezone.utc).replace(tzinfo=None)
            date_bucket = dt_ts.date()
            await self.kline_repo.insert_kline(symbol, interval, date_bucket, dt_ts, k["open"], k["high"], k["low"], k["close"], k["volume"])
        logger.info(f"Backfill complete: Saved {len(klines)} klines for {symbol} ({interval})")
