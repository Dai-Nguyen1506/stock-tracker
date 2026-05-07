# 🚀 High-Performance Crypto & Stock Tracker with AI Assistant

[![Python](https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge&logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Cassandra](https://img.shields.io/badge/Cassandra-4.0-blue?style=for-the-badge&logo=apachecassandra)](https://cassandra.apache.org/)
[![Docker](https://img.shields.io/badge/Docker-Enabled-blue?style=for-the-badge&logo=docker)](https://www.docker.com/)

A comprehensive financial market monitoring system capable of processing tens of thousands of data points per second with ultra-low latency, integrated with an intelligent AI Assistant (RAG).

---

## ✨ Key Features

- 📡 **Real-time Ingestion:** Monitor 400+ cryptocurrency pairs from **Binance** and financial news streams from **Alpaca** in real time.
- ⚡ **Ultra-fast with Cassandra:** **Leverages Acsylla (C++ Driver)** to achieve write speeds of tens of thousands of records within milliseconds
- 🤖 **AI Financial Assistant:** An intelligent chatbot powered by **Retrieval-Augmented Generation**, retrieving news and price data from Cassandra/ChromaDB to provide investment insights.
- 📊 **Interactive Dashboard:** Professional candlestick charts powered by Lightweight Charts and a real-time order book updating every 100ms.
- 📈 **Performance Benchmarking:** A benchmarking tool for directly measuring and comparing the performance of Cassandra and PostgreSQL.

---

## 📂 Project Directory Structure

```text
stock-tracker/
├── backend/
│   ├── ingestion/             # Data ingestion workers (Binance, Alpaca, Discovery)
│   ├── core/                  # Database connection configuration (Cassandra, Postgres, Redis, VectorDB)
│   ├── routers/               # API Endpoints (Market data, AI Chatbot)
│   └── main.py                # Backend API entry point
├── frontend/                  # ReactJS + Vite App
│   ├── src/
│   │   ├── components/        # Candlestick Chart, Orderbook, Chatbot, Sidebar
│   │   └── api.js             # Client API connection
├── docs/                      # Project documentation
│   └── PROJECT_DOCUMENTATION.md
├── docker-compose.yml         # Orchestration for all services
```

---

## 🛠 Tech Stack

- **Backend:** FastAPI, Python 3.11, Acsylla (Cassandra), Asyncpg (Postgres).
- **Frontend:** ReactJS, Vite, TailwindCSS, Lightweight Charts.
- **Database:**
  - **Apache Cassandra:** Primary time-series storage (Candles, Depth).
  - **PostgreSQL:** Verification data storage (Benchmarking).
  - **Redis:** High-speed Pub/Sub and Cache.
  - **ChromaDB:** Vector Database for AI News Analysis.
- **API Providers:**
  - [Binance API](https://binance-docs.github.io/apidocs/spot/en/): Market data.
  - [Alpaca API](https://alpaca.markets/docs/): Real-time financial news.
  - [Google Gemini API](https://ai.google.dev/): AI brain.

---

## 🚀 Installation & Setup

The project is completely packaged with Docker, you only need one command to launch the entire system.

### 1. Clone the project
```bash
git clone https://github.com/Dai-Nguyen1506/stock-tracker.git
cd stock-tracker
```

### 2. Configure environment variables
Copy `.env.example` to `.env` and fill in your API Keys (See the guide to get Keys below).
```bash
cp .env.example .env
```

### 3. Launch with Docker
```bash
docker compose up -d --build
```
Access: `http://localhost:5173`

### 4. Stop Docker Services
To stop all services:
```bash
docker compose stop
```

To stop and remove all containers:
```bash
docker compose down
```

To remove all containers, volumes, and images:
```bash
docker compose down -v
```

---

## 📖 Usage Guide

### 1. View Charts & Change Timeframes
- Use the **Control** panel on the right to select trading symbols and timeframes (1m, 5m, 1h, etc.).
- Candlestick charts and Order Book (Depth Chart) will automatically update in real-time via WebSocket.

### 2. Retrieve History (Infinite Scroll)
- **Drag the chart to the left:** When you drag the chart into the past, the system will automatically call the API to fetch data from Cassandra.
- **Auto-Backfill:** If Cassandra lacks data, the system calls the Binance API to backfill and save to the database silently.

### 3. AI Assistant (Financial Chatbot)
- Enter a question in the chat box (Example: "What's the status of BTC today?").
- The AI will automatically search for news in ChromaDB and fetch the latest prices from Cassandra to provide insights.

### 4. Performance Dashboard (Sidebar)
- Observe 5 metrics at the top to know the current Read/Write speed of the system.
- Use the **DB Dashboard** section to run test cases `Ping` (Measure Read speed) or `Copy` (Measure Write speed) directly.

---

## 🔑 API Key Configuration Guide

The system requires 2 main types of Keys to operate with full features:

### 1. Alpaca API Key (Market News)
- Visit [Alpaca Markets](https://alpaca.markets/) and register an account (Free).
- Go to **Dashboard** -> **Generate New API Key**.
- You will receive `API Key ID` and `Secret Key`. Fill them in `.env`.

### 2. Google Gemini API Key (AI Brain)
- Visit [Google AI Studio](https://aistudio.google.com/).
- Click the **Get API Key** button.
### 3. Database Configuration (Default)
These parameters are pre-configured in `docker-compose.yml`. If you run directly on your machine (not via Docker), fill in the following values in `.env`:

- **PostgreSQL:** `postgresql://user:password@localhost:5432/market_data`
- **Cassandra:** Host is `localhost`, Port `9042`.
- **Redis:** `redis://localhost:6379`
- **ChromaDB:** Host `localhost`, Port `8000`.

---

## 📞 Contact & Contributions
If you encounter any issues or want to contribute new features, please create an **Issue** or submit a **Pull Request**.

- **Author:** Dai Nguyen
- **Repo:** [Dai-Nguyen1506/stock-tracker](https://github.com/Dai-Nguyen1506/stock-tracker)

---
*Note: This project is for learning and research purposes on Big Data systems and AI. Be careful when using it in real trading.*