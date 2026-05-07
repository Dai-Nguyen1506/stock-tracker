# Performance Benchmarking: Cassandra vs PostgreSQL

The system includes built-in benchmarking tools to measure and compare real-world performance between Apache Cassandra and PostgreSQL.

## 1. Write Performance
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

## 2. Read/Query Performance
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
