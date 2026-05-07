import json
import threading
import time
import requests
import websocket

# ── Config ─────────────────────────────────────────────────────────────────────
SYMBOLS   = ["BTCUSDT"]
REST_BASE = "https://api.binance.com"
WS_BASE   = "wss://stream.binance.com:9443/stream"

# 1. REST – Historical OHLCV klines

def fetch_klines(symbol: str, interval: str = "1h", limit: int = 10) -> list:

    url = f"{REST_BASE}/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()

    candles = []
    for k in resp.json():
        candles.append({
            "open_time" : k[0],   # ms timestamp
            "open"      : float(k[1]),
            "high"      : float(k[2]),
            "low"       : float(k[3]),
            "close"     : float(k[4]),
            "volume"    : float(k[5]),
            "close_time": k[6],
        })
    return candles


def demo_historical():
    print("=" * 60)
    print(" HISTORICAL KLINES (REST)")
    print("=" * 60)
    for sym in SYMBOLS:
        candles = fetch_klines(sym, interval="1h", limit=3)
        print(f"\n  {sym} — last 3 hourly candles:")
        for c in candles:
            print(f"    O={c['open']:.2f}  H={c['high']:.2f}  "
                  f"L={c['low']:.2f}  C={c['close']:.2f}  Vol={c['volume']:.2f}")


# 2. WebSocket – Real-time Aggregate Trades

def on_trade(ws, message):
    data   = json.loads(message)
    stream = data.get("stream", "")
    event  = data.get("data", {})

    if event.get("e") == "aggTrade":
        sym    = event["s"]
        price  = float(event["p"])
        qty    = float(event["q"])
        side   = " SELL " if event["m"] else " BUY "
        print(f"  {side}  {sym}  price={price:.4f}  qty={qty:.6f}")


def demo_trade_stream(duration_seconds: int = 15):
    """Subscribe to aggregate trade stream for all configured symbols."""
    streams = "/".join(f"{s.lower()}@aggTrade" for s in SYMBOLS)
    url = f"{WS_BASE}?streams={streams}"

    print("\n" + "=" * 60)
    print(f"REAL-TIME TRADE STREAM ({duration_seconds}s)")
    print("=" * 60)

    ws = websocket.WebSocketApp(url, on_message=on_trade)
    t  = threading.Thread(target=ws.run_forever, daemon=True)
    t.start()
    time.sleep(duration_seconds)
    ws.close()
    print("  [Trade stream closed]")

# 3. WebSocket – Order Book Depth

def on_depth(ws, message):
    data  = json.loads(message)
    event = data.get("data", {})

    if event.get("e") == "depthUpdate":
        sym  = event["s"]
        bids = event["b"][:3]   # top 3 bids
        asks = event["a"][:3]   # top 3 asks
        print(f"\n  ORDER BOOK UPDATE — {sym}")
        print(f"    Top asks (sell): {[(float(p), float(q)) for p, q in asks]}")
        print(f"    Top bids (buy) : {[(float(p), float(q)) for p, q in bids]}")


def demo_order_book(duration_seconds: int = 15):
    """Subscribe to order book diff depth stream."""
    streams = "/".join(f"{s.lower()}@depth" for s in SYMBOLS)
    url = f"{WS_BASE}?streams={streams}"

    print("\n" + "=" * 60)
    print(f" ORDER BOOK STREAM ({duration_seconds}s)")
    print("=" * 60)

    ws = websocket.WebSocketApp(url, on_message=on_depth)
    t  = threading.Thread(target=ws.run_forever, daemon=True)
    t.start()
    time.sleep(duration_seconds)
    ws.close()
    print("  [Order book stream closed]")


# Entry point

if __name__ == "__main__":
    # 1. Historical data via REST
    demo_historical()

    # 2. Live trades for 5 seconds
    demo_trade_stream(duration_seconds=5)

    # 3. Order book updates for 5 seconds
    demo_order_book(duration_seconds=5)

    print("\n Binance demo complete.")
