# 📈 Stock & Crypto Tracking System — Project Plan

> **Stack chính:** FastAPI · Apache Cassandra · Acsylla · Docker · VectorDB · RAG AI Chatbot

---

## 🗂️ Tổng quan dự án

Hệ thống theo dõi chứng khoán và tiền điện tử theo thời gian thực, tích hợp AI chatbot thông minh có khả năng phân tích tin tức và dữ liệu thị trường thông qua RAG (Retrieval-Augmented Generation).

### Nguồn dữ liệu
| Nguồn | Loại dữ liệu | Thư viện/API |
|---|---|---|
| HOSE, HNX, UPCOM | Chứng khoán Việt Nam | `vnstock3` |
| Binance | Tiền điện tử | Binance API (REST + WebSocket) |
| Báo tài chính VN | Tin tức chứng khoán VN | `vnstock_news` |
| CryptoPanic | Tin tức crypto | CryptoPanic API |

---

## 🏗️ Kiến trúc hệ thống tổng thể

```
┌─────────────────────────────────────────────────────────────────┐
│                          FRONTEND                               │
│              (React / Next.js Dashboard)                        │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTP / WebSocket
┌────────────────────────▼────────────────────────────────────────┐
│                      FASTAPI BACKEND                            │
│   ┌──────────────┐  ┌──────────────┐  ┌───────────────────┐    │
│   │ Stock Router │  │ Crypto Router│  │   RAG / Chat API  │    │
│   └──────┬───────┘  └──────┬───────┘  └─────────┬─────────┘    │
└──────────┼─────────────────┼───────────────────┼──────────────┘
           │                 │                   │
┌──────────▼─────────────────▼──────┐  ┌────────▼────────────────┐
│         Apache Cassandra          │  │       VectorDB           │
│   (Time-series market data)       │  │  (Qdrant / Chroma /      │
│   via Acsylla (async driver)      │  │   Weaviate)              │
└───────────────────────────────────┘  └─────────────────────────┘
           │                                      │
┌──────────▼──────────────┐         ┌─────────────▼──────────────┐
│  Data Ingestion Workers  │         │      Embedding Service     │
│  vnstock3 · Binance API  │         │  (news → vector chunks)    │
└──────────────────────────┘         └────────────────────────────┘
```

---

## 📦 Giai đoạn 1: Thiết lập cơ sở hạ tầng

### Mục tiêu
Dựng môi trường Docker đầy đủ: FastAPI + Cassandra + Acsylla + Frontend chạy được local.

### Docker Compose Structure

```
project/
├── docker-compose.yml
├── docker-compose.dev.yml
├── .env
├── backend/
│   ├── Dockerfile
│   ├── main.py
│   ├── core/
│   │   ├── config.py
│   │   └── cassandra.py        # Acsylla connection pool
│   ├── routers/
│   │   ├── stocks.py
│   │   └── crypto.py
│   └── requirements.txt
├── frontend/
│   ├── Dockerfile
│   └── ...
└── cassandra/
    └── init.cql                # Keyspace & table init scripts
```

### docker-compose.yml (skeleton)

```yaml
version: "3.9"

services:
  cassandra:
    image: cassandra:4.1
    container_name: cassandra
    ports:
      - "9042:9042"
    environment:
      CASSANDRA_CLUSTER_NAME: "StockCluster"
      CASSANDRA_DC: "dc1"
      MAX_HEAP_SIZE: "512M"
      HEAP_NEWSIZE: "128M"
    volumes:
      - cassandra_data:/var/lib/cassandra
    healthcheck:
      test: ["CMD", "cqlsh", "-e", "describe keyspaces"]
      interval: 30s
      timeout: 10s
      retries: 10

  backend:
    build: ./backend
    container_name: fastapi
    ports:
      - "8000:8000"
    environment:
      CASSANDRA_HOST: cassandra
      CASSANDRA_PORT: 9042
    depends_on:
      cassandra:
        condition: service_healthy
    volumes:
      - ./backend:/app

  frontend:
    build: ./frontend
    container_name: frontend
    ports:
      - "3000:3000"
    depends_on:
      - backend

volumes:
  cassandra_data:
```

### FastAPI + Acsylla connection (core/cassandra.py)

```python
import acsylla
from core.config import settings

_session: acsylla.Session | None = None

async def get_session() -> acsylla.Session:
    global _session
    if _session is None:
        cluster = acsylla.create_cluster(
            [settings.CASSANDRA_HOST],
            port=settings.CASSANDRA_PORT,
            protocol_version=4,
        )
        _session = await cluster.create_session(keyspace="market_data")
    return _session
```

### Cassandra Keyspace Init

```cql
CREATE KEYSPACE IF NOT EXISTS market_data
  WITH replication = {
    'class': 'NetworkTopologyStrategy',
    'dc1': 1
  };
```

### Checklist Giai đoạn 1
- [ ] Docker Compose chạy thành công, Cassandra healthy
- [ ] FastAPI kết nối Cassandra qua Acsylla (async)
- [ ] Endpoint `/health` trả về trạng thái kết nối DB
- [ ] Frontend hiển thị được trang chủ dashboard (mock data)
- [ ] Hot-reload backend và frontend trong dev mode

---

## 📊 Giai đoạn 2: Thu thập & hiển thị dữ liệu

### Mục tiêu
Đổ dữ liệu thật từ vnstock3 (chứng khoán VN) và Binance API (crypto) vào Cassandra, hiển thị lên frontend.

### 2.1 Thiết kế schema Cassandra

**Nguyên tắc:** Cassandra query-first — thiết kế bảng theo cách truy vấn, không theo quan hệ.

```cql
-- Dữ liệu OHLCV chứng khoán VN (partition by symbol + date bucket)
CREATE TABLE market_data.vn_ohlcv (
    symbol      TEXT,
    date_bucket DATE,               -- partition key phụ để tránh wide rows
    timestamp   TIMESTAMP,
    open        DECIMAL,
    high        DECIMAL,
    low         DECIMAL,
    close       DECIMAL,
    volume      BIGINT,
    PRIMARY KEY ((symbol, date_bucket), timestamp)
) WITH CLUSTERING ORDER BY (timestamp DESC)
  AND compaction = {'class': 'TimeWindowCompactionStrategy',
                    'compaction_window_unit': 'DAYS',
                    'compaction_window_size': 7};

-- Dữ liệu OHLCV crypto (Binance)
CREATE TABLE market_data.crypto_ohlcv (
    symbol      TEXT,
    interval    TEXT,               -- '1m', '5m', '1h', '1d'
    date_bucket DATE,
    open_time   TIMESTAMP,
    open        DECIMAL,
    high        DECIMAL,
    low         DECIMAL,
    close       DECIMAL,
    volume      DECIMAL,
    close_time  TIMESTAMP,
    PRIMARY KEY ((symbol, interval, date_bucket), open_time)
) WITH CLUSTERING ORDER BY (open_time DESC)
  AND compaction = {'class': 'TimeWindowCompactionStrategy',
                    'compaction_window_unit': 'DAYS',
                    'compaction_window_size': 1};

-- Giá realtime / tick data
CREATE TABLE market_data.price_tick (
    symbol      TEXT,
    source      TEXT,               -- 'vnstock' | 'binance'
    ts          TIMESTAMP,
    price       DECIMAL,
    volume      BIGINT,
    PRIMARY KEY ((symbol, source), ts)
) WITH CLUSTERING ORDER BY (ts DESC)
  AND default_time_to_live = 86400;  -- TTL 1 ngày cho tick data

-- Danh sách symbols đang theo dõi
CREATE TABLE market_data.watchlist (
    user_id     UUID,
    symbol      TEXT,
    source      TEXT,
    added_at    TIMESTAMP,
    PRIMARY KEY (user_id, symbol, source)
);
```

### 2.2 Data Ingestion Workers

```python
# workers/vnstock_worker.py
import asyncio
from vnstock3 import Vnstock

async def ingest_historical(symbol: str, session):
    stock = Vnstock().stock(symbol=symbol, source='VCI')
    df = stock.quote.history(start='2020-01-01', end='2024-12-31', interval='1D')
    
    stmt = await session.create_prepared("""
        INSERT INTO market_data.vn_ohlcv 
        (symbol, date_bucket, timestamp, open, high, low, close, volume)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """)
    
    batch = acsylla.create_batch_logged()
    for _, row in df.iterrows():
        date_bucket = row['time'].date()
        bound = stmt.bind()
        bound.bind_list([symbol, date_bucket, row['time'],
                         row['open'], row['high'], row['low'],
                         row['close'], row['volume']])
        batch.add_statement(bound)
    
    await session.execute_batch(batch)

# workers/binance_worker.py — WebSocket realtime
from binance import AsyncClient, BinanceSocketManager

async def stream_binance(symbols: list[str], session):
    client = await AsyncClient.create()
    bm = BinanceSocketManager(client)
    
    streams = [f"{s.lower()}@kline_1m" for s in symbols]
    async with bm.multiplex_socket(streams) as stream:
        async while True:
            msg = await stream.recv()
            kline = msg['data']['k']
            if kline['x']:  # candle closed
                await save_kline(kline, session)
```

### 2.3 API Endpoints

```
GET  /api/v1/stocks/{symbol}/history?start=&end=&interval=
GET  /api/v1/stocks/{symbol}/latest
GET  /api/v1/crypto/{symbol}/history?interval=1h&limit=200
GET  /api/v1/crypto/{symbol}/ticker
WS   /ws/crypto/{symbol}          — realtime price stream
WS   /ws/stocks/{symbol}          — realtime price stream
POST /api/v1/watchlist             — thêm vào danh sách theo dõi
GET  /api/v1/watchlist/{user_id}   — lấy danh sách theo dõi
```

### 2.4 Frontend Dashboard

Các component cần xây dựng:
- **CandlestickChart** — dùng TradingView Lightweight Charts hoặc recharts
- **WatchlistPanel** — danh sách cổ phiếu / crypto đang theo dõi
- **PriceTicker** — giá realtime qua WebSocket
- **MarketOverview** — top gainers/losers trong ngày
- **VolumeChart** — biểu đồ volume theo thời gian

### Checklist Giai đoạn 2
- [ ] Schema Cassandra tạo thành công với TWCS compaction
- [ ] Script backfill historical data chạy được (vnstock3 + Binance)
- [ ] WebSocket realtime price stream hoạt động
- [ ] Candlestick chart hiển thị dữ liệu thật
- [ ] API pagination với `page_state` (Cassandra paging token)

---

## ⚡ Giai đoạn 3: Tối ưu Cassandra

### 3.1 Data Modeling Optimization

| Kỹ thuật | Mô tả | Áp dụng cho |
|---|---|---|
| **Time bucketing** | Chia partition theo ngày/tuần/tháng | OHLCV, tick data |
| **Denormalization** | Tạo nhiều bảng cho nhiều query pattern | Watchlist, summary |
| **Materialized Views** | Tự động đồng bộ view thứ cấp | Tìm kiếm theo ngày |
| **TTL (Time-To-Live)** | Tự xoá dữ liệu cũ | Tick data, cache |
| **Counter tables** | Đếm lượt xem, giao dịch | Analytics |

### 3.2 Compaction Strategy

```cql
-- Time-series data: dùng TWCS (tốt nhất cho dữ liệu thời gian)
ALTER TABLE market_data.vn_ohlcv
WITH compaction = {
    'class': 'TimeWindowCompactionStrategy',
    'compaction_window_unit': 'DAYS',
    'compaction_window_size': 7,
    'expired_sstable_check_frequency_seconds': 600
};

-- Dữ liệu ít update, nhiều read: dùng LCS
ALTER TABLE market_data.watchlist
WITH compaction = {'class': 'LeveledCompactionStrategy'};
```

### 3.3 Read/Write Tuning

```python
# Consistency level theo use case
# Realtime ticker: fast read, eventual consistency
result = await session.execute(stmt, consistency_level=acsylla.Consistency.LOCAL_ONE)

# Lệnh giao dịch quan trọng: strong consistency
result = await session.execute(stmt, consistency_level=acsylla.Consistency.LOCAL_QUORUM)

# Batch insert: unlogged batch (cùng partition)
batch = acsylla.create_batch_unlogged()  # Nhanh hơn logged batch ~3x
```

### 3.4 Prepared Statements & Connection Pool

```python
# Cache prepared statements — QUAN TRỌNG cho performance
class CassandraRepo:
    _prepared: dict = {}
    
    async def get_prepared(self, query: str):
        if query not in self._prepared:
            self._prepared[query] = await self.session.create_prepared(query)
        return self._prepared[query]
```

### 3.5 Cassandra JVM Tuning (docker-compose)

```yaml
cassandra:
  environment:
    MAX_HEAP_SIZE: "2G"          # 1/4 RAM, tối đa 8G
    HEAP_NEWSIZE: "400M"         # 100M per CPU core
    JVM_OPTS: >
      -XX:+UseG1GC
      -XX:G1RSetUpdatingPauseTimePercent=5
      -XX:MaxGCPauseMillis=500
      -XX:+PrintGCDetails
```

### 3.6 Indexing Strategy

```cql
-- SAI: secondary index trên low-cardinality column → OK
-- SAI: secondary index trên high-cardinality (timestamp) → TRÁNH

-- Dùng SAI (Storage-Attached Index) cho tìm kiếm flexible
CREATE CUSTOM INDEX ON market_data.vn_ohlcv (close)
USING 'StorageAttachedIndex';

-- Tốt hơn: tạo bảng summary riêng
CREATE TABLE market_data.daily_summary (
    symbol      TEXT,
    date        DATE,
    open        DECIMAL,
    close       DECIMAL,
    high        DECIMAL,
    low         DECIMAL,
    volume      BIGINT,
    change_pct  DECIMAL,
    PRIMARY KEY (date, change_pct, symbol)
) WITH CLUSTERING ORDER BY (change_pct DESC, symbol ASC);
```

### 3.7 Monitoring

```yaml
# Thêm vào docker-compose
prometheus:
  image: prom/prometheus:latest
  
grafana:
  image: grafana/grafana:latest
  ports:
    - "3001:3000"

cassandra-exporter:
  image: criteord/cassandra_exporter:latest
  environment:
    CASSANDRA_HOST: cassandra
```

**Metrics quan trọng cần theo dõi:**
- `cassandra_read_latency_p99` — độ trễ đọc P99
- `cassandra_write_latency_p99` — độ trễ ghi P99
- `cassandra_compaction_pending_tasks` — hàng đợi compaction
- `cassandra_memtable_live_data_size` — dữ liệu trong memtable
- `cassandra_hints_in_progress` — hints đang chờ (nếu node down)

### 3.8 Checklist tối ưu

- [ ] TWCS compaction cho tất cả time-series tables
- [ ] Prepared statements được cache, không tạo lại mỗi request
- [ ] Unlogged batch cho same-partition inserts
- [ ] TTL cho tick data và cache tables
- [ ] Connection pool đủ lớn (min 4, max = 2 × CPU cores)
- [ ] Cassandra JVM heap = 1/4 RAM
- [ ] Grafana dashboard theo dõi latency P99
- [ ] Partition size < 100MB (kiểm tra với `nodetool tablestats`)

---

## 🧠 Giai đoạn 4: Tích hợp VectorDB

### Mục tiêu
Lưu và tìm kiếm tin tức tài chính theo ngữ nghĩa (semantic search) phục vụ cho RAG.

### 4.1 Lựa chọn VectorDB

| VectorDB | Ưu điểm | Nhược điểm | Phù hợp |
|---|---|---|---|
| **Qdrant** | Hiệu năng cao, Docker dễ dàng, filter mạnh | Ít tài liệu tiếng Việt | ✅ Khuyến nghị |
| **Chroma** | Đơn giản, Python-native | Chưa production-ready | Dev/prototype |
| **Weaviate** | GraphQL API, module phong phú | Nặng hơn | Enterprise |
| **pgvector** | Tận dụng PostgreSQL | Kém hơn về vector search | Nếu đã có PG |

**→ Khuyến nghị: Qdrant** — hiệu năng tốt, filter theo metadata (symbol, date, source) mạnh, dễ Docker.

### 4.2 Docker Compose mở rộng

```yaml
qdrant:
  image: qdrant/qdrant:latest
  container_name: qdrant
  ports:
    - "6333:6333"
    - "6334:6334"
  volumes:
    - qdrant_data:/qdrant/storage
  environment:
    QDRANT__SERVICE__GRPC_PORT: 6334
```

### 4.3 Schema VectorDB

**Collection: `vn_stock_news`** (từ vnstock_news)
```python
from qdrant_client.models import VectorParams, Distance

await qdrant.create_collection(
    collection_name="vn_stock_news",
    vectors_config=VectorParams(size=768, distance=Distance.COSINE),
)

# Metadata payload mỗi document:
{
    "id": "uuid",
    "symbol": "VNM",           # hoặc [] nếu tin tổng quan
    "source": "cafef.vn",
    "title": "...",
    "content": "...",
    "published_at": "2024-01-15T08:00:00Z",
    "sentiment": "positive",   # optional, từ phân tích NLP
    "tags": ["earnings", "dividend"]
}
```

**Collection: `crypto_news`** (từ CryptoPanic)
```python
await qdrant.create_collection(
    collection_name="crypto_news",
    vectors_config=VectorParams(size=768, distance=Distance.COSINE),
)

# Payload:
{
    "id": "uuid",
    "currencies": ["BTC", "ETH"],
    "title": "...",
    "content": "...",
    "published_at": "...",
    "panic_score": 0.75,       # CryptoPanic sentiment score
    "votes": {"positive": 10, "negative": 2}
}
```

### 4.4 News Ingestion Pipeline

```python
# pipeline/news_ingestion.py
from sentence_transformers import SentenceTransformer
from vnstock_news import VnstockNews  # giả định API
import httpx

model = SentenceTransformer('keepitreal/vietnamese-sbert')  # model tiếng Việt

async def ingest_vn_news(session_qdrant):
    news_client = VnstockNews()
    articles = await news_client.get_latest(limit=100)
    
    for article in articles:
        text = f"{article['title']} {article['content']}"
        embedding = model.encode(text).tolist()
        
        await session_qdrant.upsert(
            collection_name="vn_stock_news",
            points=[PointStruct(
                id=article['id'],
                vector=embedding,
                payload={
                    "symbol": article.get('symbols', []),
                    "title": article['title'],
                    "content": article['content'][:2000],
                    "published_at": article['published_at'],
                    "source": article['source'],
                }
            )]
        )

async def ingest_crypto_news():
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://cryptopanic.com/api/v1/posts/",
            params={"auth_token": CRYPTOPANIC_TOKEN, "public": "true"}
        )
        posts = resp.json()['results']
    # ... embed và upsert tương tự
```

### 4.5 Scheduler (APScheduler)

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()
scheduler.add_job(ingest_vn_news,   'interval', minutes=30)
scheduler.add_job(ingest_crypto_news, 'interval', minutes=15)
scheduler.start()
```

### Checklist Giai đoạn 4
- [ ] Qdrant chạy trong Docker, collections tạo thành công
- [ ] Embedding model tiếng Việt hoạt động (vietnamese-sbert hoặc PhoBERT)
- [ ] Pipeline thu thập tin tức từ vnstock_news chạy định kỳ
- [ ] Pipeline thu thập từ CryptoPanic API chạy định kỳ
- [ ] Semantic search endpoint hoạt động: `/api/v1/news/search?q=...&symbol=VNM`
- [ ] Filter theo symbol và khoảng thời gian hoạt động đúng

---

## 🤖 Giai đoạn 5: RAG AI Chatbot

### 5.1 Kiến trúc RAG

```
User Question
      │
      ▼
┌─────────────────┐
│  Query Rewriter  │  (LLM rewrites question for better retrieval)
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────┐
│         Hybrid Retriever        │
│  ┌──────────────┐  ┌──────────┐ │
│  │ Qdrant Search│  │ Cassandra│ │
│  │ (semantic)   │  │(price)   │ │
│  └──────────────┘  └──────────┘ │
└─────────────┬───────────────────┘
              │
              ▼
┌─────────────────────┐
│   Context Builder   │  (merge + rerank retrieved docs)
└──────────┬──────────┘
           │
           ▼
┌──────────────────────────────────────┐
│             LLM Generator            │
│  System prompt + context + question  │
│  (OpenAI GPT-4 / Claude / local LLM) │
└──────────────────────────────────────┘
           │
           ▼
      Final Answer (streaming)
```

### 5.2 RAG Pipeline

```python
# rag/pipeline.py
from langchain_community.vectorstores import Qdrant
from langchain.chains import ConversationalRetrievalChain

class StockRAGPipeline:
    def __init__(self, qdrant_client, cassandra_session, llm):
        self.qdrant = qdrant_client
        self.db = cassandra_session
        self.llm = llm
    
    async def retrieve_context(self, query: str, symbol: str | None = None):
        # 1. Semantic search từ VectorDB
        filter_condition = None
        if symbol:
            filter_condition = Filter(
                must=[FieldCondition(key="symbol", match=MatchAny(any=[symbol]))]
            )
        
        news_results = await self.qdrant.search(
            collection_name="vn_stock_news",
            query_vector=self.embed(query),
            query_filter=filter_condition,
            limit=5,
            with_payload=True
        )
        
        # 2. Lấy dữ liệu giá từ Cassandra
        price_data = await self.get_recent_prices(symbol) if symbol else None
        
        return self.build_context(news_results, price_data)
    
    async def chat(self, messages: list, symbol: str | None = None):
        user_query = messages[-1]['content']
        context = await self.retrieve_context(user_query, symbol)
        
        system_prompt = f"""Bạn là chuyên gia phân tích tài chính AI.
Hãy trả lời dựa trên thông tin thị trường và tin tức được cung cấp.
Luôn ghi rõ nguồn và thời gian của thông tin.

## Dữ liệu thị trường:
{context}
"""
        # Stream response
        async for chunk in self.llm.astream(system_prompt, messages):
            yield chunk
```

### 5.3 Chat API Endpoints

```
POST /api/v1/chat
     Body: { messages: [...], symbol?: "VNM", context_type: "stock|crypto|both" }
     Response: SSE stream

GET  /api/v1/chat/history/{session_id}
DELETE /api/v1/chat/history/{session_id}

POST /api/v1/analyze/{symbol}
     — Phân tích tự động: giá + tin tức + sentiment
```

### 5.4 Prompt Engineering

```python
SYSTEM_PROMPTS = {
    "stock_analysis": """
Bạn là chuyên gia phân tích chứng khoán Việt Nam với 20 năm kinh nghiệm.
Khi phân tích, hãy:
1. Nhận xét xu hướng giá dựa trên dữ liệu OHLCV được cung cấp
2. Tóm tắt tin tức quan trọng ảnh hưởng đến cổ phiếu
3. Đưa ra nhận định ngắn hạn (1-2 tuần) và trung hạn (1-3 tháng)
4. LUÔN kèm disclaimer: "Đây là phân tích tham khảo, không phải lời khuyên đầu tư"
Trả lời bằng tiếng Việt, rõ ràng và có cấu trúc.
""",
    "crypto_analysis": """
Bạn là chuyên gia phân tích thị trường crypto.
Sử dụng dữ liệu Binance và tin tức từ CryptoPanic được cung cấp để:
1. Phân tích on-chain signals và sentiment
2. Nhận xét về Fear & Greed Index
3. Xác định các mức hỗ trợ/kháng cự quan trọng
Trả lời ngắn gọn, sử dụng bullet points.
"""
}
```

### 5.5 Frontend Chat UI

Components cần xây dựng:
- **ChatWindow** — giao diện chat với streaming response
- **SymbolContext** — chọn cổ phiếu/crypto để chat có context
- **AnalysisPanel** — tự động sinh báo cáo phân tích
- **NewsTimeline** — hiển thị tin tức liên quan trong chat

### Checklist Giai đoạn 5
- [ ] RAG pipeline lấy đúng context từ Qdrant + Cassandra
- [ ] Streaming response qua SSE hoạt động mượt mà
- [ ] Chat có memory (lưu lịch sử conversation)
- [ ] Reranking kết quả retrieval trước khi đưa vào LLM
- [ ] Disclaimer tự động kèm theo mọi phân tích tài chính
- [ ] UI chat responsive, hỗ trợ markdown rendering

---

## 🔧 Cấu trúc thư mục đầy đủ (dự kiến giai đoạn 5)

```
stock-tracker/
├── docker-compose.yml
├── docker-compose.prod.yml
├── .env.example
├── README.md
│
├── backend/
│   ├── Dockerfile
│   ├── main.py
│   ├── requirements.txt
│   ├── core/
│   │   ├── config.py
│   │   ├── cassandra.py
│   │   └── qdrant.py
│   ├── routers/
│   │   ├── stocks.py
│   │   ├── crypto.py
│   │   ├── news.py
│   │   └── chat.py
│   ├── workers/
│   │   ├── vnstock_worker.py
│   │   ├── binance_worker.py
│   │   ├── vn_news_worker.py
│   │   └── cryptopanic_worker.py
│   ├── rag/
│   │   ├── pipeline.py
│   │   ├── retriever.py
│   │   ├── prompts.py
│   │   └── embeddings.py
│   └── models/
│       ├── stock.py
│       └── crypto.py
│
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   └── src/
│       ├── components/
│       │   ├── Chart/
│       │   ├── Watchlist/
│       │   └── Chat/
│       └── pages/
│
└── cassandra/
    ├── init.cql
    └── migrations/
```

---

## 🚀 Lộ trình & Timeline dự kiến

| Giai đoạn | Thời gian ước tính | Kết quả bàn giao |
|---|---|---|
| **1 - Infrastructure** | 3–5 ngày | Docker stack chạy, health check OK |
| **2 - Data Pipeline** | 1–2 tuần | Dashboard hiển thị data thật |
| **3 - Cassandra Tuning** | 3–5 ngày | Latency P99 < 10ms cho read |
| **4 - VectorDB** | 1 tuần | News search semantic hoạt động |
| **5 - RAG Chatbot** | 1–2 tuần | Chatbot phân tích được cổ phiếu |
| **Tổng cộng** | **~6–7 tuần** | Full system production-ready |

---

## 📋 Dependencies chính

```txt
# Backend (requirements.txt)
fastapi>=0.110.0
uvicorn[standard]>=0.27.0
acsylla>=0.3.0
python-binance>=1.0.19
vnstock3>=0.3.0
qdrant-client>=1.7.0
sentence-transformers>=2.5.0
langchain>=0.1.0
langchain-community>=0.0.20
apscheduler>=3.10.0
httpx>=0.26.0
pydantic-settings>=2.1.0
```

---

*Tài liệu này sẽ được cập nhật liên tục khi dự án tiến triển qua từng giai đoạn.*