# Crypto Dashboard

**Note:** This project is currently for **Frontend Testing only** using mock data. Full backend and database integration will be implemented in the *main branch*.

## Quick Start (Local)
1. **Navigate to folder:** `cd frontend`
2. **Install:** `npm install`
3. **Run:** `npm run dev`
4. **Access:** `http://localhost:5173`

## Docker Run
1. **Build image:**
   ```bash
   docker build -t crypto-dash .

2. **Run container:**
   ```bash
   docker run -d -p 8080:80 --name my-dash crypto-dash .

3. Access: http://localhost:8080

## Tech Stack
* **Frontend**: React, TypeScript, Vite
* **Charting**: Lightweight Charts
* **Deployment**: Docker, Nginx

