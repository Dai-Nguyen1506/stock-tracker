# Tài liệu Kiến trúc Dự án: High-Performance Crypto/Stock Tracker & AI Assistant

Dự án này là một hệ thống theo dõi thị trường tài chính (Crypto/Stock) theo thời gian thực với hiệu năng cực cao, kết hợp cùng Trợ lý AI (Chatbot RAG) để phân tích dữ liệu và tin tức. Hệ thống được xây dựng theo kiến trúc Microservices và được đóng gói hoàn toàn bằng Docker.

---

## 1. Tổng quan Kiến trúc (Architecture Overview)

Dự án bao gồm 3 phân hệ chính:
- **Frontend (Giao diện người dùng):** Ứng dụng ReactJS (Vite) hiển thị biểu đồ nến (Klines), sổ lệnh (Orderbook) theo thời gian thực và giao diện Chatbot.
- **Ingestion Workers (Thu thập dữ liệu):** Các tiến trình chạy ngầm thu thập hàng vạn bản ghi mỗi phút từ các WebSocket (Binance, Alpaca).
- **Backend API (Xử lý trung tâm):** FastAPI cung cấp các API RESTful để truy xuất lịch sử, thống kê tốc độ (Benchmarking) và AI RAG.
- **Database Layer (Lưu trữ đa tầng):** Sử dụng kết hợp Cassandra, PostgreSQL, Redis và ChromaDB để tối ưu cho từng loại dữ liệu cụ thể.

---

## 2. Hệ sinh thái Cơ sở dữ liệu (Database Layer)

Đây là trái tim của hệ thống với sự kết hợp của 4 loại Database khác nhau:

### 2.1. Apache Cassandra (Primary Time-Series DB)
- **Vai trò:** Lưu trữ dữ liệu siêu tốc độ, khối lượng khổng lồ (Nến, Orderbook, Tin tức).
- **Tối ưu hóa (Production-grade):**
  - Sử dụng **TWCS (TimeWindowCompactionStrategy)** để tự động đóng băng dữ liệu theo ngày.
  - Phân vùng dữ liệu (Partition Key) theo `date_bucket` để tránh phình to.
  - Bật nén **LZ4 Compressor** giảm thiểu IO ổ đĩa.
  - Thuật toán **UNLOGGED BATCH** nhóm dữ liệu theo từng mã (`symbol`) giúp chèn hàng chục nghìn bản ghi chỉ trong chưa tới 2 giây.
  - Truy vấn **Asynchronous Parallel (`asyncio.gather`)** để quét nhiều Partition song song.

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

## 5. Hướng dẫn Vận hành (Runbook)

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
