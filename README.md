# 🚀 High-Performance Crypto & Stock Tracker with AI Assistant

[![Python](https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge&logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Cassandra](https://img.shields.io/badge/Cassandra-4.0-blue?style=for-the-badge&logo=apachecassandra)](https://cassandra.apache.org/)
[![Docker](https://img.shields.io/badge/Docker-Enabled-blue?style=for-the-badge&logo=docker)](https://www.docker.com/)

Một hệ thống theo dõi thị trường tài chính toàn diện, xử lý hàng vạn dữ liệu mỗi giây với độ trễ cực thấp, tích hợp Trợ lý AI (RAG) thông minh.

---

## ✨ Tính năng nổi bật

- 📡 **Real-time Ingestion:** Theo dõi hơn 400+ mã tiền điện tử từ **Binance** và tin tức từ **Alpaca**.
- ⚡ **Siêu tốc với Cassandra:** Tận dụng thư viện **Acsylla (C++ Driver)** để đạt tốc độ ghi hàng vạn bản ghi trong vài mili giây.
- 🤖 **AI Financial Assistant:** Chatbot sử dụng công nghệ **RAG (Retrieval-Augmented Generation)**, truy xuất tin tức và dữ liệu giá từ Cassandra/ChromaDB để tư vấn đầu tư.
- 📊 **Interactive Dashboard:** Biểu đồ nến chuyên nghiệp (Lightweight Charts), Sổ lệnh (Orderbook) cập nhật từng 100ms.
- 📈 **Performance Benchmarking:** Công cụ đo lường và so sánh trực tiếp hiệu năng giữa Cassandra và PostgreSQL.

---

## 📂 Cấu trúc Thư mục Dự án

```text
stock-tracker/
├── backend/
│   ├── ingestion/             # Các worker thu thập dữ liệu (Binance, Alpaca, Discovery)
│   ├── core/                  # Cấu hình kết nối DB (Cassandra, Postgres, Redis, VectorDB)
│   ├── routers/               # API Endpoints (Market data, AI Chatbot)
│   └── main.py                # Điểm khởi đầu của Backend API
├── frontend/                  # ReactJS + Vite App
│   ├── src/
│   │   ├── components/        # Candlestick Chart, Orderbook, Chatbot, Sidebar
│   │   └── api.js             # Client kết nối API
├── docs/                     # Tài liệu dự án
│   └── PROJECT_DOCUMENTATION.md
├── docker-compose.yml         # Orchestration cho toàn bộ dịch vụ
```

---

## 🛠 Tech Stack

- **Backend:** FastAPI, Python 3.11, Acsylla (Cassandra), Asyncpg (Postgres).
- **Frontend:** ReactJS, Vite, TailwindCSS, Lightweight Charts.
- **Database:**
  - **Apache Cassandra:** Lưu trữ Time-series chính (Nến, Depth).
  - **PostgreSQL:** Lưu trữ dữ liệu đối chứng (Benchmarking).
  - **Redis:** Pub/Sub và Cache tốc độ cao.
  - **ChromaDB:** Vector Database cho AI News Analysis.
- **API Providers:**
  - [Binance API](https://binance-docs.github.io/apidocs/spot/en/): Dữ liệu thị trường.
  - [Alpaca API](https://alpaca.markets/docs/): Tin tức tài chính thời gian thực.
  - [Google Gemini API](https://ai.google.dev/): Bộ não AI.

---

## 🚀 Cài đặt & Khởi chạy

Dự án được đóng gói hoàn toàn bằng Docker, bạn chỉ cần một câu lệnh để khởi chạy toàn bộ hệ thống.

### 1. Clone dự án
```bash
git clone https://github.com/Dai-Nguyen1506/stock-tracker.git
cd stock-tracker
```

### 2. Cấu hình biến môi trường
Copy file `.env.example` thành `.env` và điền các API Key của bạn (Xem hướng dẫn lấy Key bên dưới).
```bash
cp .env.example .env
```

### 3. Khởi chạy với Docker
```bash
docker compose up -d --build
```
Truy cập: `http://localhost:5173`

---

## 📖 Hướng dẫn sử dụng

### 1. Xem biểu đồ & Thay đổi khung thời gian
- Sử dụng bảng **Control** phía bên phải để chọn mã giao dịch (Symbol) và khung thời gian (1m, 5m, 1h...).
- Biểu đồ nến và Sổ lệnh (Depth Chart) sẽ tự động cập nhật thời gian thực qua WebSocket.

### 2. Truy xuất lịch sử (Infinite Scroll)
- **Kéo biểu đồ sang trái:** Khi bạn kéo biểu đồ về quá khứ, hệ thống sẽ tự động gọi API lấy dữ liệu từ Cassandra.
- **Auto-Backfill:** Nếu Cassandra thiếu dữ liệu, hệ thống tự gọi Binance API để bù đắp và lưu lại vào DB một cách âm thầm.

### 3. Trợ lý AI (Financial Chatbot)
- Nhập câu hỏi vào ô chat (Ví dụ: "Tình hình BTC hôm nay thế nào?").
- AI sẽ tự động lục tìm tin tức trong ChromaDB và lấy giá mới nhất từ Cassandra để đưa ra nhận định.

### 4. Dashboard Hiệu năng (Sidebar)
- Quan sát 5 ô thông số trên cùng để biết tốc độ Ghi/Đọc hiện tại của hệ thống.
- Sử dụng mục **DB Dashboard** để chạy các bài test `Ping` (Đo tốc độ Đọc) hoặc `Copy` (Đo tốc độ Ghi) trực tiếp.

---

## 🔑 Hướng dẫn lấy API Keys

Hệ thống yêu cầu 2 loại Key chính để hoạt động đầy đủ tính năng:

### 1. Alpaca API Key (Tin tức thị trường)
- Truy cập [Alpaca Markets](https://alpaca.markets/) và đăng ký tài khoản (Free).
- Vào mục **Dashboard** -> **Generate New API Key**.
- Bạn sẽ nhận được `API Key ID` và `Secret Key`. Hãy điền chúng vào `.env`.

### 2. Google Gemini API Key (Bộ não AI)
- Truy cập [Google AI Studio](https://aistudio.google.com/).
- Nhấn vào nút **Get API Key**.
### 3. Thông tin Cơ sở dữ liệu (Mặc định)
Các thông số này đã được cấu hình sẵn trong `docker-compose.yml`. Nếu bạn chạy trực tiếp trên máy (không qua Docker), hãy điền các giá trị sau vào `.env`:

- **PostgreSQL:** `postgresql://user:password@localhost:5432/market_data`
- **Cassandra:** Host là `localhost`, Port `9042`.
- **Redis:** `redis://localhost:6379`
- **ChromaDB:** Host `localhost`, Port `8000`.

---

## 📞 Liên hệ & Đóng góp
Nếu bạn gặp bất kỳ vấn đề gì hoặc muốn đóng góp tính năng mới, vui lòng tạo **Issue** hoặc gửi **Pull Request**.

- **Author:** Dai Nguyen
- **Repo:** [Dai-Nguyen1506/stock-tracker](https://github.com/Dai-Nguyen1506/stock-tracker)

---
*Lưu ý: Dự án này phục vụ mục đích học tập và nghiên cứu về hệ thống dữ liệu lớn (Big Data) và AI. Hãy cẩn trọng khi sử dụng trong giao dịch thực tế.*