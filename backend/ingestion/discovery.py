import httpx
import os
from contextlib import suppress

def get_optimized_crypto_lists(binance_raw_list, alpaca_raw_list):
    """
    Xử lý và phân loại danh sách Crypto từ Binance và Alpaca.
    - priority_list: Có ở cả 2 sàn, ưu tiên các mã 'hot'.
    - remainder_list: Chỉ có ở Binance.
    """
    
    HOT_TICKERS = ['BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'DOGE', 'ADA', 'TRX', 'LINK', 'AVAX']

    def get_base(s):
        s = s.upper()
        if '/' in s: return s.split('/')[0] # Cho Alpaca
        if s.endswith('USDT'): return s.replace('USDT', '') # Cho Binance
        return s

    binance_bases = {get_base(s) for s in binance_raw_list}
    alpaca_bases = {get_base(s) for s in alpaca_raw_list}

    both_bases = binance_bases.intersection(alpaca_bases)
    only_binance_bases = binance_bases - alpaca_bases

    priority_hot = [b for b in HOT_TICKERS if b in both_bases]
    priority_others = sorted([b for b in both_bases if b not in HOT_TICKERS])
    priority_final_bases = priority_hot + priority_others

    remainder_final_bases = sorted(list(only_binance_bases))

    result = {
        "priority_list": [
            {"base": b, "alpaca": f"{b}/USD", "binance": f"{b.lower()}usdt"} 
            for b in priority_final_bases
        ],
        "remainder_list": [
            {"base": b, "binance": f"{b.lower()}usdt"} 
            for b in remainder_final_bases
        ]
    }

    return result


async def get_active_usdt_symbols(limit=1000):
    """Lấy danh sách mã USDT đang TRADING trên Binance."""
    url = "https://api.binance.com/api/v3/exchangeInfo"
    async with httpx.AsyncClient() as client:
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
            print(f"Lỗi khi lấy danh sách mã Binance: {e}")
            return []

async def get_alpaca_crypto_symbols(api_key, secret_key):
    """Lấy danh sách mã Crypto từ Alpaca."""
    if not api_key or not secret_key:
        print("Cảnh báo: Chưa cấu hình ALPACA_API_KEY/SECRET_KEY. Trả về mảng rỗng.")
        return []
        
    url = "https://paper-api.alpaca.markets/v2/assets"
    headers = {
        "accept": "application/json",
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": secret_key
    }
    params = {
        "asset_class": "crypto", 
        "status": "active"
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            crypto_assets = response.json()
            return [asset['symbol'] for asset in crypto_assets]
        except Exception as e:
            print(f"Lỗi khi cấu hình/kết nối Alpaca REST: {e}")
            return []

async def run_discovery_bootstrap():
    """Chạy đồng bộ hoá và bootstrap danh sách symbols khi khởi động app."""
    # Thường lấy từ biến môi trường (Core config)
    API_KEY = os.getenv("ALPACA_API_KEY_ID", "")
    SECRET_KEY = os.getenv("ALPACA_API_SECRET_KEY", "")
    
    binance_symbols = await get_active_usdt_symbols(limit=100)
    alpaca_symbols = await get_alpaca_crypto_symbols(API_KEY, SECRET_KEY)
    
    # Nếu Alpaca không lấy được thì tạo mock từ danh sách Binance để test trước
    if not alpaca_symbols:
        alpaca_symbols = ["BTC/USD", "ETH/USD", "SOL/USD"]
        
    processed_data = get_optimized_crypto_lists(binance_symbols, alpaca_symbols)
    
    print(f"✅ Đã phân loại: {len(processed_data['priority_list'])} priority (có ở 2 kho) & {len(processed_data['remainder_list'])} remainder (chỉ Binance).")
    return processed_data

if __name__ == "__main__":
    import asyncio
    loop = asyncio.get_event_loop()
    data = loop.run_until_complete(run_discovery_bootstrap())
    if data["priority_list"]:
        print(f"Ví dụ đầu priority: {data['priority_list'][:3]}")
