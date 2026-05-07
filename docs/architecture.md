# Project Architecture Documentation: High-Performance Crypto/Stock Tracker & AI Assistant

This project is a real-time financial market tracking system (Crypto/Stock) with extreme performance, integrated with an AI Assistant (RAG Chatbot) for data and news analysis. The system is built using a Microservices architecture and is fully containerized with Docker.

---

## 1. Architecture Overview

The project consists of 3 main components:
- **Frontend (User Interface):** A ReactJS (Vite) application displaying real-time candlestick charts (Klines), orderbooks, and a Chatbot interface.
- **Ingestion Workers (Data Collection):** Background processes collecting tens of thousands of records per minute from WebSockets (Binance, Alpaca).
- **Backend API (Central Processing):** FastAPI providing RESTful APIs for historical data retrieval, performance statistics (Benchmarking), and AI RAG.
- **Database Layer (Multi-tier Storage):** A combination of Cassandra, PostgreSQL, Redis, and ChromaDB optimized for specific data types.

### System Architecture Diagram
```text
=============================================================================
                       [ EXTERNAL API SYSTEM ]
      (Binance REST API)    (Binance WebSocket)       (Alpaca WebSocket)
      - Historical Klines   - Price/Trade/Depth       - News + Historical API
=============================================================================
                                  │
                                  ▼
=============================================================================
                    [ BACKEND LAYER (FastAPI / Python) ]
 
 1. DATA INGESTION (Real-time Flow):
    ├─ Binance WS ──> Kline Calculation ──────┐
    ├─ Binance WS ──> Depth Processing ───────┼──> Push via Custom WS Server
    └─ Alpaca WS  ──> News Collection (JSON) ─┘
 
 2. DATABASE LAYER (Cassandra):
    ├─ `klines` Table (Primary Key: symbol, timestamp)
    ├─ `news`   Table (Primary Key: symbol, timestamp)
    └─ `depth`  Table (Using TTL = 24h for auto-deletion)
 
 3. API SERVICE (On-Demand Flow):
    └─ `/history` API: Intelligent Read/Write Logic
       ├─ UI Scroll Left -> Call `/history`
       ├─ Cache Hit (DB) -> Read DB -> UI
       └─ Cache Miss     -> Fetch Binance -> Write DB -> Read DB -> UI
=============================================================================
                                  │
      (HTTP REST API for History) │ (WebSocket for Real-time)
                                  ▼
=============================================================================
                          [ FRONTEND LAYER (WEB UI) ]
 
 ┌─────────────────────┬────────────────────────────────┬───────────────────┐
 │ COLUMN 1: INSIGHTS  │ COLUMN 2: TRADING DASHBOARD    │ COLUMN 3: CONTROL │
 │                     │                                │                   │
 │ [ REALTIME NEWS ]   │ [ CANDLESTICK CHART ]          │ [ WATCHLIST ]     │
 │ - Auto-updates from │ - Initial: Load 500 candles    │ - Top Priority    │
 │   Alpaca News WS    │ - Scroll: Auto-load + Show     │ - All Binance     │
 │ - Filter by Symbol  │   DB Read/Write Speed          │                   │
 │                     │ - Seamless WS Integration      │                   │
 │                     ├────────────────────────────────┤                   │
 │ [ AI CHATBOT ]      │ [ MARKET DEPTH CHART ]         │ [ DB DASHBOARD ]  │
 │ - RAG combined with │ - Dynamic Green/Red Hills from │ - Select Interval │
 │   Cassandra (News/  │   Depth data (Real-time UI)    │ - DB Statistics:  │
 │   Price) for advice │ - Per-second fluctuations      │   R/W Speed       │
 └─────────────────────┴────────────────────────────────┴───────────────────┘
```

> **Key Architectural Enhancements:**
> 1. **Pipeline Model (Left -> Right):** Visualizes the data flow from collection and processing to storage and visualization.
> 2. **Discovery Service:** `discovery.py` module automatically scans Binance API to find and allocate a list of 400+ trading pairs for Workers.
> 3. **Auto Backfill Mechanism:** When querying history and Cassandra has missing data, the API automatically calls Binance to fill the gaps and asynchronously saves it back to the database.
> 4. **Detailed AI RAG Flow:** Three-step processing: Retrieve context from ChromaDB -> Extract market values from Cassandra -> Assemble Prompt for LLM.

---

## Directory Structure

```text
stock-tracker/
├── backend/
│   ├── ingestion/             # Background data collection workers
│   │   ├── binance_ws.py      # Kline and Orderbook collection
│   │   ├── alpaca_ws.py       # Financial news collection
│   │   └── discovery.py       # Automatic symbol list scanning
│   ├── routers/               # API Endpoints
│   │   ├── market.py          # Market data & Benchmark API
│   │   └── chat.py            # RAG Chatbot API
│   ├── utils/                 # Database connection utilities
│   │   ├── cassandra_client.py
│   │   ├── pg_client.py
│   │   ├── redis_client.py
│   │   └── llm_client.py
│   ├── Dockerfile             # Backend Dockerfile
│   └── requirements.txt       # Python dependencies
├── frontend/                  # User Interface
│   ├── src/
│   │   ├── components/        # Chart, Orderbook, Chatbot, Sidebar
│   │   ├── App.jsx            # Main Layout
│   │   └── api.js             # Backend connection
│   └── Dockerfile             # Frontend Dockerfile
├── docker-compose.yml         # System orchestration file
└── README.md                  # Project overview (being redesigned)
```
