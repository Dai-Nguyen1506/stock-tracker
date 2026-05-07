# Database Layer

The core of the system utilizes a combination of 4 different databases:

## 1. Apache Cassandra (Primary Time-Series DB) - Optimization Focus
**Role:** High-speed storage for massive time-series data (Klines, Orderbook, News). The heart of the system.

### A. Schema Design & Principles
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

### B. Performance Optimization Techniques
The project applies all production-grade Best Practices for Cassandra to optimize Read/Write performance:

1. **Acsylla Library (C++ Driver Core):** Uses `acsylla` instead of pure Python `cassandra-driver`. Acsylla is an asynchronous wrapper based on the **DataStax C++ Driver**, allowing OS-level I/O execution for speeds up to 10x faster than traditional drivers.
2. **Memory Buffer & Flush (Bulk Insert):** Python workers do not perform single inserts. They aggregate data in RAM and `flush()` in batches every 60 seconds, maximizing Cassandra's high-throughput ingestion.
3. **UNLOGGED BATCH by Partition:** Uses `create_batch_unlogged()` to group hundreds of records into a single execution unit. This technique eliminates redundant transaction logging, reducing CPU load and disk I/O.
4. **Parallel Concurrency:** Combines `asyncio.gather` with **Semaphore (1000)** to launch hundreds of concurrent write requests, utilizing network bandwidth and multi-core cluster processing.
5. **Prepared Statements:** All Insert commands are pre-compiled on the Server to save CPU resources on SQL parsing.
6. **TimeWindowCompactionStrategy (TWCS):** A dedicated compaction strategy for Time-Series data, managing SSTable files by time windows and efficiently handling expired data (TTL).
7. **LZ4 Compression:** Direct table-level compression to minimize disk I/O bytes.

## 2. PostgreSQL (Benchmarking DB)
- **Role:** Reference database to compare Read/Write performance against Cassandra.
- **Optimization:** Uses the `asyncpg` library and `executemany` (Binary COPY) at the C layer, achieving Bulk Insert speeds of ~40,000 rows per second.

## 3. Redis (In-memory Cache)
- **Role:** High-speed temporary state storage.
- **Function:** Shares global ingestion speeds (Trade Speed, Depth Speed, Latency) between background Workers and the Backend API for real-time UI updates.

## 4. ChromaDB (Vector Database)
- **Role:** Stores embeddings for News to power the Chatbot.
- **Configuration:** Cache and AI models are mounted to `./.cache` on the Host for persistence, fixing permission issues and avoiding constant model reloading.
