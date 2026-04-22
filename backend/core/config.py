from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    CASSANDRA_HOST: str = "localhost"
    CASSANDRA_PORT: int = 9042
    CASSANDRA_KEYSPACE: str = "market_data"
    APP_ENV: str = "development"
    
    # Redis configuration
    REDIS_URL: str = "redis://localhost:6379"

    # ChromaDB configuration
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8000
    
    # API Keys
    ALPACA_API_KEY_ID: str = ""
    ALPACA_API_SECRET_KEY: str = ""

    class Config:
        env_file = ".env"

settings = Settings()