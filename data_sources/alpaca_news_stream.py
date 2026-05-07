import asyncio
import os
from alpaca.data.live import NewsDataStream
from dotenv import load_dotenv

load_dotenv()

# Credentials
ALPACA_API_KEY    = os.getenv("ALPACA_API_KEY", "YOUR_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "YOUR_SECRET_KEY")

# Handler
async def on_news(news):
    print("\n NEWS EVENT")
    print(f"  Headline : {news.headline}")
    print(f"  Summary  : {news.summary[:120]}..." if news.summary else "")
    print(f"  Author   : {news.author}")
    print(f"  Symbols  : {news.symbols}")
    print(f"  Time     : {news.created_at}")
    print(f"  URL      : {news.url}")

# Main
def main():
    stream = NewsDataStream(
        api_key=ALPACA_API_KEY,
        secret_key=ALPACA_SECRET_KEY,
    )

    # Subscribe to all news ("*") or narrow to specific tickers:
    # e.g. stream.subscribe_news(on_news, "BTC", "ETH")
    stream.subscribe_news(on_news, "*")

    print(" Connecting to Alpaca News WebSocket …")
    print("   Press Ctrl+C to stop.\n")
    stream.run()


if __name__ == "__main__":
    main()
