from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    CASSANDRA_HOST: str = "localhost"
    CASSANDRA_PORT: int = 9042
    CASSANDRA_KEYSPACE: str = "market_data"
    APP_ENV: str = "development"

    class Config:
        env_file = ".env"

settings = Settings()