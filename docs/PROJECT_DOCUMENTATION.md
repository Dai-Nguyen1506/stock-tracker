# Tài liệu Kiến trúc Dự án: High-Performance Crypto/Stock Tracker & AI Assistant

Dự án này là một hệ thống theo dõi thị trường tài chính (Crypto/Stock) theo thời gian thực với hiệu năng cực cao, kết hợp cùng Trợ lý AI (Chatbot RAG) để phân tích dữ liệu và tin tức. Hệ thống được xây dựng theo kiến trúc Microservices và được đóng gói hoàn toàn bằng Docker.

---

## 1. Tổng quan Kiến trúc (Architecture Overview)

Dự án bao gồm 3 phân hệ chính:
- **Frontend (Giao diện người dùng):** Ứng dụng ReactJS (Vite) hiển thị biểu đồ nến (Klines), sổ lệnh (Orderbook) theo thời gian thực và giao diện Chatbot.
- **Ingestion Workers (Thu thập dữ liệu):** Các tiến trình chạy ngầm thu thập hàng vạn bản ghi mỗi phút từ các WebSocket (Binance, Alpaca).
- **Backend API (Xử lý trung tâm):** FastAPI cung cấp các API RESTful để truy xuất lịch sử, thống kê tốc độ (Benchmarking) và AI RAG.
- **Database Layer (Lưu trữ đa tầng):** Sử dụng kết hợp Cassandra, PostgreSQL, Redis và ChromaDB để tối ưu cho từng loại dữ liệu cụ thể.

### Sơ đồ Luồng hoạt động (System Architecture Diagram)
```text
=============================================================================
                       [ HỆ THỐNG EXTERNAL API ]
      (Binance REST API)    (Binance WebSocket)       (Alpaca WebSocket)
      - Lấy nến quá khứ    - Lấy giá/trade/depth     - Lấy News + API quá khứ
=============================================================================
                                  │
                                  ▼
=============================================================================
                    [ BACKEND LAYER (FastAPI / Python) ]

 1. DATA INGESTION (Luồng Real-time):
    ├─ Binance WS ──> Tính Nến (K-lines) ──────┐
    ├─ Binance WS ──> Lấy Depth ───────────────┼──> Đẩy qua WS Server của bạn
    └─ Alpaca WS  ──> Lấy News (JSON) ─────────┘

 2. DATABASE LAYER (Cassandra):
    ├─ Bảng `klines` (Primary Key: symbol, timestamp)
    ├─ Bảng `news`   (Primary Key: symbol, timestamp)
    └─ Bảng `depth`  (Sử dụng TTL = 24h để tự động xóa)

 3. API SERVICE (Luồng On-Demand):
    └─ API `/history`: Xử lý Logic "Đọc/Ghi" thông minh
       ├─ Kéo UI sang trái -> Gọi `/history`
       ├─ Cache Hit (Có trong DB) -> Đọc DB -> UI
       └─ Cache Miss (Không có) -> Kéo Binance -> Ghi DB -> Đọc DB -> UI
=============================================================================
                                  │
      (HTTP REST API cho Lịch sử) │ (WebSocket cho Real-time)
                                  ▼
=============================================================================
                         [ FRONTEND LAYER (WEB UI) ]

 ┌─────────────────────┬────────────────────────────────┬───────────────────┐
 │ CỘT 1: INSIGHTS     │ CỘT 2: TRADING DASHBOARD       │ CỘT 3: CONTROL    │
 │                     │                                │                   │
 │ [ TIN TỨC REALTIME ]│ [ BIỂU ĐỒ NẾN (CANDLESTICK) ]  │ [ WATCHLIST ]     │
 │ - Tự nhảy khi có    │ - Khởi tạo: Load 500 nến       │ - Top Priority    │
 │   tin từ Alpaca     │ - Kéo trái: Auto-load + Hiện   │ - All Binance     │
 │ - Lọc theo Symbol   │   tốc độ Read/Write DB         │                   │
 │                     │ - Khớp nối liền mạch WS        │                   │
 │                     ├────────────────────────────────┤                   │
 │ [ AI CHATBOT ]      │ [ MARKET DEPTH CHART ]         │ [ DB DASHBOARD ]  │
 │ - RAG kết hợp với   │ - Vẽ 2 sườn đồi Xanh/Đỏ từ     │ - Chọn Interval   │
 │   Cassandra (News/  │   dữ liệu Depth (UI real-time) │ - Thống kê DB:    │
 │   Price) để tư vấn  │ - Biến động theo giây          │   Tốc độ ghi/đọc  │
 └─────────────────────┴────────────────────────────────┴───────────────────┘
```

> **Các bổ sung quan trọng trong Kiến trúc:**
> 1. **Mô hình Pipeline (Trái -> Phải):** Thể hiện luồng di chuyển của dữ liệu từ khi được thu thập, xử lý, lưu trữ cho đến khi hiển thị trực quan cho người dùng.
> 2. **Discovery Service:** Bổ sung module `discovery.py` tự động quét API Binance để tìm và cấp phát danh sách 400+ mã đang giao dịch cho Worker.
> 3. **Cơ chế Auto Backfill:** Đường chấm đứt từ `Market API` ngược về `Binance HTTP`. Khi truy vấn lịch sử mà Cassandra bị thủng/thiếu dữ liệu, API tự động gọi Binance để lấy thêm (điền khuyết) và ngầm ghi lại vào Database.
> 4. **Luồng AI RAG chi tiết:** Phân tách rõ 3 bước xử lý của Chatbot: Tìm ngữ cảnh từ ChromaDB -> Rút trích giá trị thị trường từ Cassandra -> Lắp ráp Prompt gửi cho LLM.

---

## 1.5. Cấu trúc Thư mục Dự án (Directory Structure)

```text
stock-tracker/
├── backend/
│   ├── ingestion/             # Các worker thu thập dữ liệu ngầm
│   │   ├── binance_ws.py      # Lấy dữ liệu Nến và Sổ lệnh
│   │   ├── alpaca_ws.py       # Lấy dữ liệu Tin tức
│   │   └── discovery.py       # Quét tự động danh sách mã symbol
│   ├── routers/               # Các API Endpoints
│   │   ├── market.py          # API dữ liệu thị trường & Benchmark
│   │   └── chat.py            # API cho RAG Chatbot
│   ├── utils/                 # Các tiện ích kết nối DB
│   │   ├── cassandra_client.py
│   │   ├── pg_client.py
│   │   ├── redis_client.py
│   │   └── llm_client.py
│   ├── Dockerfile             # Docker file cho backend
│   └── requirements.txt       # Dependencies Python
├── frontend/                  # Giao diện người dùng
│   ├── src/
│   │   ├── components/        # Chart, Orderbook, Chatbot, Sidebar
│   │   ├── App.jsx            # Layout chính
│   │   └── api.js             # Kết nối backend
│   └── Dockerfile             # Docker file cho frontend
├── docker-compose.yml         # File khởi chạy toàn bộ hệ thống
└── PROJECT_DOCUMENTATION.md   # Tài liệu dự án
```

---

## 2. Hệ sinh thái Cơ sở dữ liệu (Database Layer)

Đây là trái tim của hệ thống với sự kết hợp của 4 loại Database khác nhau:

### 2.1. Apache Cassandra (Primary Time-Series DB) - Chuyên đề Tối ưu hóa
**Vai trò:** Lưu trữ dữ liệu time-series siêu tốc độ, khối lượng khổng lồ (Nến, Orderbook, Tin tức). Đây là trái tim của hệ thống.

#### A. Thiết kế Lược đồ (Schema Design) & Nguyên lý
Trong Cassandra, việc thiết kế bảng phải dựa trên **Truy vấn (Query-Driven Design)**, không phải dựa trên quan hệ thực thể như SQL.

**1. Bảng `market_data.klines` (Dữ liệu Nến)**
- **Schema:** 
  ```sql
  PRIMARY KEY ((symbol, date_bucket, interval), start_time)
  WITH CLUSTERING ORDER BY (start_time DESC)
  ```
- **Mục đích:** Lưu trữ giá mở/đóng/đỉnh/đáy của từng nến.
- **Tại sao thiết kế như vậy?**
  - **Partition Key `(symbol, date_bucket, interval)`:** Kỹ thuật **Date Bucketing**. Nếu chỉ dùng `symbol`, sau 1 năm dữ liệu của mã (vd: BTC) sẽ dồn cục vào 1 Node gây nghẽn cổ chai (Wide Partition). Bằng cách chèn thêm `date_bucket` (chuỗi ngày `YYYY-MM-DD`), dữ liệu mỗi ngày của 1 mã sẽ sinh ra 1 Partition mới, phân tán đều tải trên toàn bộ cụm.
  - **Clustering Key `start_time DESC`:** Sắp xếp nến mới nhất lên đầu ngay trên mức ổ cứng vật lý. Khi Frontend yêu cầu "100 nến gần nhất", hệ thống chỉ cần đọc một mạch từ đĩa cứng xuống mà không tốn CPU để `ORDER BY` trong RAM.

**2. Bảng `market_data.orderbook` (Sổ lệnh)**
- **Schema:** `PRIMARY KEY ((symbol, date_bucket), timestamp) WITH CLUSTERING ORDER BY (timestamp DESC)`
- **Mục đích:** Lưu trữ trạng thái Orderbook (Bids/Asks) siêu tốc từng giây. Thiết kế Partition Key Date Bucketing tương tự nến.

#### B. Các kỹ thuật Tối ưu hóa Hiệu năng (Performance Optimization)
Dự án đã áp dụng toàn bộ các Best Practices chuẩn Production cho Cassandra để tối ưu hóa Ghi/Đọc:

1. **Thư viện Acsylla (C++ Driver Core):** Sử dụng `acsylla` thay vì `cassandra-driver` thuần Python. Acsylla là một bản wrapper bất đồng bộ (async) dựa trên **DataStax C++ Driver**, cho phép thực thi I/O ở tầng hệ điều hành, mang lại tốc độ vượt trội gấp hàng chục lần so với driver truyền thống.
2. **Memory Buffer & Flush (Bulk Insert):** Worker Python không `INSERT` lắt nhắt. Nó gom dữ liệu trên RAM và thực hiện `flush()` theo lô (Batch) mỗi 60 giây, tận dụng tối đa khả năng nuốt dữ liệu lớn của Cassandra.
3. **UNLOGGED BATCH theo Partition:** Sử dụng `create_batch_unlogged()` để gộp hàng trăm bản ghi vào một đơn vị thực thi duy nhất. Kỹ thuật này loại bỏ việc ghi transaction log dư thừa, giúp giảm tải CPU và tăng tốc độ ghi đĩa đáng kể.
4. **Cơ chế Ghi song song (Parallel Concurrency):** Kết hợp `asyncio.gather` cùng với **Semaphore (500)** để tung ra hàng trăm yêu cầu ghi đồng thời. Điều này giúp hệ thống tận dụng tối đa băng thông mạng và khả năng xử lý đa nhân của cụm Cassandra.
5. **Prepared Statements:** Mọi câu lệnh Insert đều được biên dịch trước (Compiled) một lần trên Server để tiết kiệm tài nguyên CPU cho việc Parse SQL.
6. **TimeWindowCompactionStrategy (TWCS):** Thuật toán nén chuyên dụng cho dữ liệu Time-Series, giúp quản lý file SSTable theo cửa sổ thời gian và tự động dọn dẹp dữ liệu hết hạn (TTL) một cách hiệu quả.
7. **LZ4 Compression:** Nén dữ liệu trực tiếp ở tầng Table để giảm thiểu dung lượng byte phải ghi xuống ổ cứng (I/O Disk).

### 2.2. PostgreSQL (Benchmarking DB)
- **Vai trò:** Database đối chứng để so sánh hiệu năng Ghi/Đọc với Cassandra.
- **Tối ưu hóa:** Sử dụng thư viện `asyncpg` siêu tốc cùng giao thức `executemany` (Binary COPY) ở tầng C, mang lại tốc độ Bulk Insert xấp xỉ 1 giây cho 40.000 dòng.

### 2.3. Redis (In-memory Cache)
- **Vai trò:** Lưu trữ trạng thái tạm thời, siêu nhanh.
- **Công năng:** Chia sẻ các biến tốc độ (Global Ingestion Speed: Trade Speed, Depth Speed, Latency) giữa các Worker (chạy ngầm) và Backend API để đẩy lên giao diện theo thời gian thực.

### 2.4. ChromaDB (Vector Database)
- **Vai trò:** Lưu trữ embeddings cho Tin tức (News) nhằm phục vụ Chatbot.
- **Cấu hình:** Dữ liệu cache và AI model được mount ra thư mục vật lý `./.cache` trên Host để bảo toàn vĩnh viễn dữ liệu khi khởi động lại Docker, khắc phục lỗi Permission và Tải lại model liên tục.

---

## 3. Các Thành phần Cốt lõi (Core Components)

### `backend/ingestion/binance_ws.py`
- Worker kết nối WebSocket tới Binance, đăng ký hơn 400 mã tiền điện tử.
- Nhận luồng dữ liệu Klines và Depth (Orderbook).
- Cơ chế **Buffer & Flush (Mỗi 1 phút)**: Gom dữ liệu trên RAM, sau đó tự động sắp xếp (Sort) theo mã và đóng thành các lô (Batches) để ghi thẳng vào Cassandra và Postgres cùng lúc.

### `backend/ingestion/alpaca_ws.py`
- Worker kết nối tới Alpaca API để bắt luồng tin tức tài chính.
- Mã hóa nội dung tin tức (Embeddings) và lưu song song vào Cassandra (để tra cứu truyền thống) và ChromaDB (để AI phân tích ngữ nghĩa).

### `backend/routers/market.py`
- Cung cấp API lịch sử Klines cho biểu đồ Frontend.
- Tự động **Backfill (Điền khuyết)**: Nếu Cassandra thiếu dữ liệu cũ, API tự động gọi Binance HTTP để lấy thêm, trả về Frontend và ngầm lưu lại vào Cassandra cho các lần sau.
- Chứa các Endpoints phục vụ việc "Ping Test" (Đo tốc độ Đọc) và "Copy Test" (Đo tốc độ Ghi) cho cả Cassandra và Postgres.

### `backend/routers/chat.py`
- Endpoint phục vụ Trợ lý AI tài chính.
- **RAG (Retrieval-Augmented Generation):** Khi người dùng đặt câu hỏi, hệ thống tự trích xuất mã Symbol, tìm tin tức liên quan trong ChromaDB, lấy lịch sử giá từ Cassandra và ghép thành một Prompt hoàn chỉnh.
- Sử dụng mô hình `llama-3.3-70b-versatile` của Groq (Siêu tốc) và cơ chế Fallback tự động sang Gemini nếu Groq quá tải.

---

## 4. Giao diện (Frontend)
- Được xây dựng bằng React và Vite.
- **DepthChart & Candlestick:** Tích hợp thư viện Lightweight Charts / Recharts.
- **Dashboard Sidebar:** Hiển thị trực quan tốc độ dòng chảy dữ liệu (Bản ghi/Phút), độ trễ (Latency) của Cassandra vs Postgres. Có các nút tương tác để thực thi Load Testing (Ping, Copy) ngay trên trình duyệt.

---

## 5. Báo cáo Hiệu năng (Performance Benchmarking) Cassandra vs PostgreSQL

Hệ thống được tích hợp sẵn công cụ Benchmarking trực tiếp để đo lường và so sánh hiệu năng thực tế giữa Apache Cassandra (Primary Time-Series DB) và PostgreSQL (Relational DB) thông qua giao diện.

### 5.1. Hiệu năng Ghi (Write Performance)
Đo lường thời gian đổ dữ liệu thực tế (Lô ~40,000 bản ghi gồm Nến & Orderbook):

| Lần đo | Cassandra (Parallel) | PostgreSQL (Bulk) |
|:---:|:---:|:---:|
| 1 | 116.50 ms | 1064.03 ms |
| 2 | 381.37 ms | 1081.91 ms |
| 3 | 105.53 ms | 874.58 ms |
| 4 | 93.02 ms | 776.52 ms |
| 5 | 104.06 ms | 792.00 ms |
| **Trung bình** | **~160.10 ms** | **~917.80 ms** |

**Nhận xét:**
- **Cassandra:** Thể hiện sức mạnh áp đảo nhờ cơ chế ghi song song (Parallelism) thông qua Acsylla C++ Driver. Tốc độ ghi nhanh gấp **gần 6 lần** so với PostgreSQL. Ngay cả ở lần chạy chậm nhất (381ms), nó vẫn nhanh gấp 3 lần đối thủ.
- **PostgreSQL:** Tốc độ ghi khá ổn định quanh mức 800ms-1s nhưng bị giới hạn bởi kiến trúc ghi tuần tự vào đĩa cứng, không thể bứt phá lên mức dưới 500ms cho khối lượng dữ liệu này.

### 5.2. Hiệu năng Đọc/Truy xuất (Read/Query Performance)
Đo lường thời gian truy xuất lịch sử (Lô ~90,000 dòng dữ liệu nến):

| Lần đo | Cassandra | PostgreSQL |
|:---:|:---:|:---:|
| 1 | 102 ms | 185 ms |
| 2 | 93 ms | 158 ms |
| 3 | 118 ms | 141 ms |
| 4 | 111 ms | 119 ms |
| 5 | 89 ms | 126 ms |
| **Trung bình** | **~102.6 ms** | **~145.8 ms** |

**Nhận xét:**
- **Cassandra:** Duy trì sự ổn định cực cao dưới 120ms. Do dữ liệu được sắp xếp vật lý theo thời gian (`Clustering Order`), việc đọc một dải nến dài là cực kỳ nhẹ nhàng với Cassandra.
- **PostgreSQL:** Có xu hướng nhanh dần ở các lần đo sau (do cơ chế Shared Buffers/Caching của Postgres), nhưng vẫn chậm hơn Cassandra khoảng 40%.

**Kết luận cuối cùng:**
Hệ thống đã chứng minh Cassandra là lựa chọn "vô đối" cho bài toán Ingestion dữ liệu thị trường. Việc sử dụng Cassandra làm DB chính giúp UI không bao giờ bị trễ (lag) khi dữ liệu đổ về dồn dập, đồng thời cho phép người dùng kéo biểu đồ về quá khứ với độ phản hồi tức thì.
PostgreSQL đóng vai trò là DB dự phòng và đối chứng, hoàn thành tốt nhiệm vụ lưu trữ bền vững nhưng không phù hợp để làm Database hiển thị thời gian thực cho quy mô dữ liệu lớn.

---

## 6. Hướng dẫn Vận hành (Runbook)

Hệ thống được đóng gói 100% bằng Docker Compose:

1. **Khởi động toàn bộ cụm:**
   ```bash
   docker compose up -d
   ```
2. **Theo dõi tốc độ thu thập dữ liệu (Ingestion):**
   ```bash
   docker compose logs ingestion-binance -f
   ```
3. **Kiểm tra trạng thái Backend:**
   ```bash
   docker compose logs backend -f
   ```

*Hệ thống tự động khởi tạo Database Schema (Bảng, Cột) trong lần khởi chạy đầu tiên thông qua container `cassandra-init`.*
