import asyncio
import json
import time
import redis.asyncio as redis
import sys
import os

# Add backend to path to use config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config import settings

async def send_fake_news(symbol: str, headline: str):
    """
    Sends a mock news item to the Redis 'live:news' channel to test UI notifications.
    """
    print(f"Connecting to Redis at {settings.REDIS_URL}...")
    r = redis.from_url(settings.REDIS_URL)
    
    payload = {
        "type": "news",
        "symbol": symbol.upper(),
        "headline": f"[TEST] {headline}",
        "url": "https://google.com",
        "timestamp": int(time.time() * 1000)
    }
    
    print(f"Publishing fake news for {symbol}: {headline}")
    await r.publish("live:news", json.dumps(payload))
    print("Done! Check your browser UI now.")
    await r.aclose()

if __name__ == "__main__":
    symbol = sys.argv[1] if len(sys.argv) > 1 else "BTC"
    headline = sys.argv[2] if len(sys.argv) > 2 else "Bitcoin breaks $100k in a simulation!"
    
    asyncio.run(send_fake_news(symbol, headline))
