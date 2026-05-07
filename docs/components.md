# Core Components

## `backend/ingestion/binance_ws.py`
- Connects via WebSocket to Binance, subscribing to 400+ crypto pairs.
- Receives Klines and Depth (Orderbook) streams.
- **Buffer & Flush (Every 1 minute):** Aggregates data in RAM, sorts by symbol, and flushes in batches to Cassandra and Postgres simultaneously.

## `backend/ingestion/alpaca_ws.py`
- Connects to Alpaca API for real-time financial news.
- Encodes news content (Embeddings) and saves to both Cassandra (traditional lookup) and ChromaDB (AI semantic analysis).

## `backend/routers/market.py`
- Provides historical Kline API for Frontend charts.
- **Auto Backfill:** If Cassandra is missing old data, the API calls Binance HTTP, returns it to the Frontend, and saves it to Cassandra in the background.
- Contains endpoints for "Ping Test" (Read speed) and "Copy Test" (Write speed) for both Cassandra and Postgres.

## `backend/routers/chat.py`
- Endpoint for the AI Financial Assistant.
- **RAG (Retrieval-Augmented Generation):** Extracts symbols from user queries, finds related news in ChromaDB, retrieves price history from Cassandra, and assembles a complete Prompt for the LLM.
- Uses Groq's `llama-3.3-70b-versatile` (Extreme speed) with an automatic Fallback to Gemini if Groq is overloaded.
