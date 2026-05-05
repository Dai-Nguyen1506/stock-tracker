import httpx
import os
from core.config import settings
from core.logger import logger

def get_optimized_crypto_lists(binance_raw_list: list, alpaca_raw_list: list) -> dict:
    """
    Processes and categorizes crypto lists from Binance and Alpaca.
    """
    HOT_TICKERS = ['BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'DOGE', 'ADA', 'TRX', 'LINK', 'AVAX']

    def get_base(s: str) -> str:
        s = s.upper()
        if '/' in s: return s.split('/')[0]
        if s.endswith('USDT'): return s.replace('USDT', '')
        return s

    binance_bases = {get_base(s) for s in binance_raw_list}
    alpaca_bases = {get_base(s) for s in alpaca_raw_list}

    both_bases = binance_bases.intersection(alpaca_bases)
    only_binance_bases = binance_bases - alpaca_bases

    priority_hot = [b for b in HOT_TICKERS if b in both_bases]
    priority_others = sorted([b for b in both_bases if b not in HOT_TICKERS])
    priority_final_bases = priority_hot + priority_others

    remainder_final_bases = sorted(list(only_binance_bases))

    return {
        "priority_list": [
            {"base": b, "alpaca": f"{b}/USD", "binance": f"{b.lower()}usdt"} 
            for b in priority_final_bases
        ],
        "remainder_list": [
            {"base": b, "binance": f"{b.lower()}usdt"} 
            for b in remainder_final_bases
        ]
    }

async def get_active_usdt_symbols(limit: int = 1000) -> list:
    """
    Retrieves the list of active USDT pairs from Binance.
    """
    url = f"{settings.BINANCE_API_URL}/exchangeInfo"
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            symbols = []
            for s in data["symbols"]:
                if s["quoteAsset"] == "USDT" and s["status"] == "TRADING":
                    symbols.append(s["symbol"].lower())
            return symbols[:limit]
        except Exception as e:
            logger.error(f"[App] Discovery - Binance fetch error: {e}")
            return []

async def get_alpaca_crypto_symbols(api_key: str, secret_key: str) -> list:
    """
    Retrieves the list of active crypto assets from Alpaca.
    """
    if not api_key or not secret_key:
        logger.warning("[App] Discovery - Alpaca keys missing.")
        return []
        
    url = f"{settings.ALPACA_API_URL}/assets"
    headers = {
        "accept": "application/json",
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": secret_key
    }
    params = {"asset_class": "crypto", "status": "active"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            crypto_assets = response.json()
            return [asset['symbol'] for asset in crypto_assets]
        except Exception as e:
            logger.error(f"[App] Discovery - Alpaca API error: {e}")
            return []

async def run_discovery_bootstrap() -> dict:
    """
    Synchronizes and categorizes market symbols on startup.
    """
    api_key = settings.ALPACA_API_KEY_ID
    secret_key = settings.ALPACA_API_SECRET_KEY
    
    binance_symbols = await get_active_usdt_symbols(limit=1000)
    alpaca_symbols = await get_alpaca_crypto_symbols(api_key, secret_key)
    
    if not alpaca_symbols:
        alpaca_symbols = ["BTC/USD", "ETH/USD", "SOL/USD"]
        
    processed_data = get_optimized_crypto_lists(binance_symbols, alpaca_symbols)
    logger.info(f"[App] Discovery: {len(processed_data['priority_list'])} priority pairs, {len(processed_data['remainder_list'])} others.")
    return processed_data

if __name__ == "__main__":
    import asyncio
    loop = asyncio.get_event_loop()
    data = loop.run_until_complete(run_discovery_bootstrap())
    if data["priority_list"]:
        print(f"Example priority symbols: {data['priority_list'][:3]}")
