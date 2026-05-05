from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    """
    Application settings and environment variables.
    """
    # Cassandra
    CASSANDRA_HOST: str = "cassandra"
    CASSANDRA_PORT: int = 9042
    CASSANDRA_KEYSPACE: str = "market_data"
    
    # Redis
    REDIS_URL: str = "redis://redis:6379/0"
    
    # PostgreSQL
    PG_URL: str = "postgresql://user:password@postgres:5432/market_data"
    
    # ChromaDB
    CHROMA_HOST: str = "chromadb"
    CHROMA_PORT: int = 8000
    
    # Binance URLs
    BINANCE_API_URL: str = "https://api.binance.com/api/v3"
    BINANCE_WS_URL: str = "wss://stream.binance.com:9443/stream"
    
    # Alpaca URLs
    ALPACA_API_URL: str = "https://paper-api.alpaca.markets/v2"
    ALPACA_DATA_URL: str = "https://data.alpaca.markets/v1beta1"
    ALPACA_WS_URL: str = "wss://stream.data.alpaca.markets/v1beta1/news"
    
    # AI Keys
    GEMINI_API_KEY: str = ""
    ALPACA_API_KEY_ID: str = ""
    ALPACA_API_SECRET_KEY: str = ""
    
    # App Settings
    APP_ENV: str = "production"
    UVICORN_WORKERS: int = 2

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()