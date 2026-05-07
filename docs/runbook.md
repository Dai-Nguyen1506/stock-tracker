# Runbook

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
