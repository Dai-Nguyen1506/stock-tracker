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

## 1.5. Directory Structure

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

---

## 2. Database Layer

The core of the system utilizes a combination of 4 different databases:

### 2.1. Apache Cassandra (Primary Time-Series DB) - Optimization Focus
**Role:** High-speed storage for massive time-series data (Klines, Orderbook, News). The heart of the system.

#### A. Schema Design & Principles
In Cassandra, table design follows **Query-Driven Design**, not entity relations like SQL.

**1. `market_data.klines` Table (Kline Data)**
- **Schema:** 
  ```sql
  PRIMARY KEY ((symbol, date_bucket, interval), start_time)
  WITH CLUSTERING ORDER BY (start_time DESC)
  ```
- **Purpose:** Stores open/high/low/close/volume for each candle.
- **Rationale:**
  - **Partition Key `(symbol, date_bucket, interval)`:** **Date Bucketing** technique. Using only `symbol` would lead to "Wide Partitions" and hotspots. Adding `date_bucket` (`YYYY-MM-DD`) distributes each day's data into a new partition, balancing load across the cluster.
  - **Clustering Key `start_time DESC`:** Physically sorts the newest candles at the top on disk. When the Frontend requests "the last 100 candles", the system reads directly from disk without RAM-intensive `ORDER BY` operations.

**2. `market_data.orderbook` Table (Orderbook)**
- **Schema:** `PRIMARY KEY ((symbol, date_bucket), timestamp) WITH CLUSTERING ORDER BY (timestamp DESC)`
- **Purpose:** Per-second high-speed storage of Orderbook states (Bids/Asks). Uses similar Date Bucketing as Klines.

#### B. Performance Optimization Techniques
The project applies all production-grade Best Practices for Cassandra to optimize Read/Write performance:

1. **Acsylla Library (C++ Driver Core):** Uses `acsylla` instead of pure Python `cassandra-driver`. Acsylla is an asynchronous wrapper based on the **DataStax C++ Driver**, allowing OS-level I/O execution for speeds up to 10x faster than traditional drivers.
2. **Memory Buffer & Flush (Bulk Insert):** Python workers do not perform single inserts. They aggregate data in RAM and `flush()` in batches every 60 seconds, maximizing Cassandra's high-throughput ingestion.
3. **UNLOGGED BATCH by Partition:** Uses `create_batch_unlogged()` to group hundreds of records into a single execution unit. This technique eliminates redundant transaction logging, reducing CPU load and disk I/O.
4. **Parallel Concurrency:** Combines `asyncio.gather` with **Semaphore (1000)** to launch hundreds of concurrent write requests, utilizing network bandwidth and multi-core cluster processing.
5. **Prepared Statements:** All Insert commands are pre-compiled on the Server to save CPU resources on SQL parsing.
6. **TimeWindowCompactionStrategy (TWCS):** A dedicated compaction strategy for Time-Series data, managing SSTable files by time windows and efficiently handling expired data (TTL).
7. **LZ4 Compression:** Direct table-level compression to minimize disk I/O bytes.

### 2.2. PostgreSQL (Benchmarking DB)
- **Role:** Reference database to compare Read/Write performance against Cassandra.
- **Optimization:** Uses the `asyncpg` library and `executemany` (Binary COPY) at the C layer, achieving Bulk Insert speeds of ~40,000 rows per second.

### 2.3. Redis (In-memory Cache)
- **Role:** High-speed temporary state storage.
- **Function:** Shares global ingestion speeds (Trade Speed, Depth Speed, Latency) between background Workers and the Backend API for real-time UI updates.

### 2.4. ChromaDB (Vector Database)
- **Role:** Stores embeddings for News to power the Chatbot.
- **Configuration:** Cache and AI models are mounted to `./.cache` on the Host for persistence, fixing permission issues and avoiding constant model reloading.

---

## 3. Core Components

### `backend/ingestion/binance_ws.py`
- Connects via WebSocket to Binance, subscribing to 400+ crypto pairs.
- Receives Klines and Depth (Orderbook) streams.
- **Buffer & Flush (Every 1 minute):** Aggregates data in RAM, sorts by symbol, and flushes in batches to Cassandra and Postgres simultaneously.

### `backend/ingestion/alpaca_ws.py`
- Connects to Alpaca API for real-time financial news.
- Encodes news content (Embeddings) and saves to both Cassandra (traditional lookup) and ChromaDB (AI semantic analysis).

### `backend/routers/market.py`
- Provides historical Kline API for Frontend charts.
- **Auto Backfill:** If Cassandra is missing old data, the API calls Binance HTTP, returns it to the Frontend, and saves it to Cassandra in the background.
- Contains endpoints for "Ping Test" (Read speed) and "Copy Test" (Write speed) for both Cassandra and Postgres.

### `backend/routers/chat.py`
- Endpoint for the AI Financial Assistant.
- **RAG (Retrieval-Augmented Generation):** Extracts symbols from user queries, finds related news in ChromaDB, retrieves price history from Cassandra, and assembles a complete Prompt for the LLM.
- Uses Groq's `llama-3.3-70b-versatile` (Extreme speed) with an automatic Fallback to Gemini if Groq is overloaded.

---

## 4. Frontend
- Built with React and Vite.
- **DepthChart & Candlestick:** Integrated Lightweight Charts / Recharts libraries.
- **Dashboard Sidebar:** Visualizes data ingestion flow (Records/Min) and Latency of Cassandra vs Postgres. Includes interactive buttons for Load Testing (Ping, Copy) directly from the browser.

---

## 5. Performance Benchmarking: Cassandra vs PostgreSQL

The system includes built-in benchmarking tools to measure and compare real-world performance between Apache Cassandra and PostgreSQL.

### 5.1. Write Performance
Measures the time to ingest a batch of ~40,000 records (Klines & Orderbook):

| Test | Cassandra (Parallel) | PostgreSQL (Bulk) |
|:---:|:---:|:---:|
| 1 | 116.50 ms | 1064.03 ms |
| 2 | 381.37 ms | 1081.91 ms |
| 3 | 105.53 ms | 874.58 ms |
| 4 | 93.02 ms | 776.52 ms |
| 5 | 104.06 ms | 792.00 ms |
| **Average** | **~160.10 ms** | **~917.80 ms** |

**Observations:**
- **Cassandra:** Dominates with parallelism via the Acsylla C++ Driver. Write speeds are nearly **6x faster** than PostgreSQL. Even its slowest run (381ms) is 3x faster than the competitor.
- **PostgreSQL:** Stable around 800ms-1s but limited by sequential disk write architecture, unable to break the 500ms barrier for this data volume.

### 5.2. Read/Query Performance
Measures retrieval time for ~90,000 rows of historical Kline data:

| Test | Cassandra | PostgreSQL |
|:---:|:---:|:---:|
| 1 | 102 ms | 185 ms |
| 2 | 93 ms | 158 ms |
| 3 | 118 ms | 141 ms |
| 4 | 111 ms | 119 ms |
| 5 | 89 ms | 126 ms |
| **Average** | **~102.6 ms** | **~145.8 ms** |

**Observations:**
- **Cassandra:** Maintains high stability under 120ms. Since data is physically sorted by time (`Clustering Order`), reading long candlestick ranges is effortless.
- **PostgreSQL:** Tends to speed up in subsequent runs due to Shared Buffers/Caching, but remains about 40% slower than Cassandra.

**Final Conclusion:**
The system proves Cassandra is the unmatched choice for market data ingestion. Using Cassandra as the primary DB ensures zero UI lag during heavy data influx while allowing instantaneous chart scrolling. PostgreSQL serves as a reliable backup and reference DB, excellent for persistent storage but unsuitable for large-scale real-time visualization.

---

## 6. Runbook

The system is 100% containerized with Docker Compose:

1. **Start the entire cluster:**
   ```bash
   docker compose up -d
   ```
2. **Monitor Ingestion speed:**
   ```bash
   docker compose logs ingestion-binance -f
   ```
3. **Check Backend status:**
   ```bash
   docker compose logs backend -f
   ```

*The system automatically initializes the Database Schema (Tables, Columns) on the first run via the `cassandra-init` container.*
