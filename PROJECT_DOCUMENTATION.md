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

1. **Memory Buffer & Flush (Bulk Insert):** Worker Python không `INSERT` lắt nhắt mỗi khi có dữ liệu từ WebSocket. Thay vào đó, nó gom trữ trên RAM. Đúng 1 phút, nó mới gọi hàm `flush()` để ghi hàng vạn bản ghi. Cassandra đặc biệt mạnh mẽ trong việc nuốt dữ liệu theo Lô khổng lồ.
2. **UNLOGGED BATCH theo Partition:** Khi `flush()`, dữ liệu được gom nhóm *chặt chẽ theo cùng một Partition Key*. Sau đó sử dụng `BEGIN UNLOGGED BATCH`. Cơ chế này báo cho Cassandra không cần ghi transaction log phân tán nội bộ, giúp tăng tốc độ Ghi lên hàng chục lần mà không làm sập Node.
3. **Prepared Statements:** Mọi câu lệnh Insert đều được biên dịch trước (Compiled) một lần trên Server. Khi chạy, Worker chỉ truyền giá trị tham số (parameters), tiết kiệm toàn bộ tài nguyên CPU dùng để Parse SQL.
4. **Asynchronous I/O (`asyncio.gather`):** Khi cần query hoặc insert nhiều partition đồng thời, hệ thống sử dụng Driver bất đồng bộ, đẩy hàng ngàn request bay đi cùng lúc trên một Thread duy nhất, tối đa hóa thông lượng mạng (Network Throughput).
5. **TimeWindowCompactionStrategy (TWCS):** Thuật toán nén dữ liệu ổ đĩa chuyên biệt cho Time-Series. Thay vì trộn lẫn, nó gộp các dữ liệu theo cửa sổ ngày thành các file SSTable riêng biệt. Khi hết hạn (TTL), Cassandra chỉ cần drop hẳn file đó thay vì phải I/O tốn kém như các DB khác.
6. **LZ4 Compression:** Bật nén LZ4 trực tiếp ở tầng Table. Chấp nhận hy sinh cực kỳ ít CPU để giảm thiểu độ lớn byte phải tương tác với ổ cứng (I/O Disk), giúp đọc/ghi tăng tốc đáng kể.

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
Việc đánh giá tốc độ ghi được thực hiện trên khối lượng lớn dữ liệu nến (Klines) và sổ lệnh (Orderbook) thu thập mỗi phút (lên đến 40k bản ghi mỗi phút):
- **Cassandra:** Chèn hàng vạn bản ghi mất khoảng **1.5 - 2.0 giây** nhờ cơ chế `UNLOGGED BATCH` phân nhóm theo `symbol` và cấu trúc Partition tối ưu theo `date_bucket`. Mặc dù tốc độ ấn tượng, nó vẫn chịu một chút Overhead do cơ chế đồng thuận phân tán.
- **PostgreSQL:** Chèn lượng dữ liệu tương đương chỉ mất khoảng **0.8 - 1.2 giây**. Sự vượt trội này đến từ việc sử dụng giao thức Binary COPY (`executemany` của `asyncpg`) thực thi ở tầng C, ghi tuần tự khối dữ liệu lớn vào một node duy nhất mà không cần bận tâm về phân tán.

### 5.2. Hiệu năng Đọc/Truy xuất (Read/Query Performance)
Quá trình đánh giá tốc độ đọc được thực hiện thông qua các bài Test truy xuất đồng thời lịch sử của toàn bộ ~400+ mã giao dịch:
- **Cassandra:** Hoàn thành truy vấn toàn bộ dữ liệu trong khoảng **0.2 - 0.4 giây**. Đây là điểm mạnh tuyệt đối của Cassandra nhờ khả năng quét song song cực nhanh thông qua `asyncio.gather` và kiến trúc phân tán ngang (Horizontally Scalable).
- **PostgreSQL:** Tốc độ truy xuất đồng thời chậm hơn rõ rệt, dao động từ **1.5 - 2.5 giây** cho khối lượng tương tự. Do kiến trúc RDBMS truyền thống và cơ chế quản lý I/O, việc quét lượng lớn dữ liệu Time-Series không thể đạt hiệu suất như hệ thống NoSQL chuyên dụng.

**Kết luận:** Hệ thống đã chứng minh được sự lựa chọn công nghệ đúng đắn: 
- **PostgreSQL** cực kỳ phù hợp cho các luồng Ghi (Bulk Insert) nguyên khối, siêu tốc cục bộ.
- **Cassandra** lại là "vua" trong việc phân tán, lưu trữ Time-Series lâu dài và cung cấp khả năng Đọc/Truy xuất đồng thời (Parallel Reads) với độ trễ cực thấp để cấp liệu liên tục cho biểu đồ và AI Chatbot.

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
