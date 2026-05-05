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