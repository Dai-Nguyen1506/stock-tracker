# Data Sources — `features/data-sources`

This branch introduces the three external data integrations that feed the trading pipeline:

| Source | What we use it for | Protocol |
|---|---|---|
| **Alpaca** | Real-time financial news stream | WebSocket |
| **Binance** | Crypto price history, live trades, order book | REST + WebSocket |
| **Google Gemini** | AI analysis of news → trade suggestions | HTTP (REST chat API) |

---

## Directory layout

```
data_sources/
├── alpaca_news_stream.py   # Alpaca news WebSocket demo
├── binance_data.py         # Binance REST history + WebSocket trades & order book
├── gemini_analysis.py      # Gemini AI news analyser + interactive chat
├── requirements.txt
└── .env.example
```

---

## Setup

### 1. Install dependencies

```bash
pip install -r data_sources/requirements.txt
```

### 2. Configure API keys

```bash
cp data_sources/.env.example .env
# Edit .env and fill in your keys
```

Load them before running any script:

```bash
export $(cat .env | xargs)
```

Or use `python-dotenv` — each script reads from environment variables automatically.

---

## Alpaca — Real-time News Stream

**File:** `alpaca_news_stream.py`

**Endpoint:** `wss://stream.data.alpaca.markets/v1beta1/news`

The Alpaca SDK's `NewsDataStream` handles authentication and reconnection. We subscribe with the `"*"` wildcard to receive news for all tickers. Each event includes:

- `headline` — article title
- `summary` — short description
- `author`, `created_at`, `url`
- `symbols` — list of related tickers (e.g. `["BTC/USD", "ETH/USD"]`)

**Run:**

```bash
python data_sources/alpaca_news_stream.py
```

**To narrow to specific symbols**, change the subscribe call:

```python
stream.subscribe_news(on_news, "BTC/USD", "ETH/USD")
```

---

## Binance — Price History, Live Trades & Order Book

**File:** `binance_data.py`

**No API key required** for public market data. The demo covers three data types:

### 1. Historical OHLCV — REST API

```
GET https://api.binance.com/api/v3/klines
```

Returns closed candlesticks for a symbol + interval. Symbols used in this demo: `BTCUSDT`, `ETHUSDT`, `SOLUSDT`, `BNBUSDT`.

```python
candles = fetch_klines("BTCUSDT", interval="1h", limit=100)
```

Available intervals: `1m 3m 5m 15m 30m 1h 4h 1d 1w`

### 2. Real-time Trades — WebSocket `aggTrade`

```
wss://stream.binance.com:9443/stream?streams=btcusdt@aggTrade/ethusdt@aggTrade/...
```

Each message contains the price, quantity, and whether it was a maker-side sell (i.e. taker buy vs taker sell). Multiple symbols are combined into a single combined stream URL to avoid opening multiple connections.

### 3. Order Book Depth — WebSocket `depth`

```
wss://stream.binance.com:9443/stream?streams=btcusdt@depth/ethusdt@depth/...
```

Streams differential order book updates (bids & asks that changed). For a full local order book you would: (1) fetch a REST snapshot, (2) buffer diff events, (3) apply diffs in sequence.

For a simpler top-of-book view use `@depth5` (top 5 levels, full snapshot every 1 s) instead.

**Run:**

```bash
python data_sources/binance_data.py
```

This will:
1. Print the last 3 hourly candles for all 4 symbols.
2. Stream live trades for 15 seconds.
3. Stream order book updates for 15 seconds.

---

## Google Gemini — AI News Analysis

**File:** `gemini_analysis.py`

**Model:** `gemini-2.0-flash` — fast, cost-efficient, supports multi-turn chat.

The system prompt instructs Gemini to act as a crypto trading analyst. Two modes are available:

### Single-turn analysis

Pass a news headline, summary, and current prices. Gemini returns:
- Bullish / Bearish / Neutral assessment
- Which assets are most affected
- Suggested entry zone, take-profit, stop-loss
- Confidence level and key risks

```python
analysis = analyse_news(
    headline="SEC approves spot Ethereum ETF",
    summary="...",
    prices={"ETHUSDT": 3120.50, "BTCUSDT": 62450.0},
)
print(analysis)
```

### Multi-turn interactive chat

Maintains conversation history so you can follow up ("what if BTC drops 5%?", "adjust the stop-loss", etc.).

```python
chat_session()   # interactive REPL
```

**Run:**

```bash
python data_sources/gemini_analysis.py
```

---

## Planned integration flow

```
Alpaca News Stream
       │  headline + symbols
       ▼
 Binance REST / WS  ──►  Current price context
       │
       ▼
  Gemini AI Chat
       │  trade plan (entry / TP / SL / confidence)
       ▼
  [Trading Engine]   ← next milestone
```

Each component runs as an independent async task; in the full system they will be wired together through an internal event bus (e.g. `asyncio.Queue` or a message broker).

---

## Rate limits & gotchas

| Source | Limit | Notes |
|---|---|---|
| Alpaca News WS | 1 connection per account | Close other sessions before connecting |
| Binance REST | 1 200 requests/min per IP | Use `X-MBX-USED-WEIGHT` header to track usage |
| Binance WS | 5 incoming messages/s | Combine symbols into one stream URL |
| Gemini API | Varies by tier | Free tier: 15 RPM / 1M TPM for Flash |

---

## Key dependencies

| Package | Purpose |
|---|---|
| `alpaca-py` | Official Alpaca SDK — news + market data streams |
| `websocket-client` | Binance WebSocket connections |
| `requests` | Binance REST API calls |
| `google-genai` | Official Google Gen AI SDK for Gemini |
| `python-dotenv` | Load `.env` credentials |
