from pydantic import BaseModel
from typing import Optional

class PingTestRequest(BaseModel):
    symbol: str
    interval: str
    limit: int = 100
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class BenchmarkResponse(BaseModel):
    read_ms: Optional[int] = 0
    write_ms: Optional[int] = 0
    rows: Optional[int] = 0
    status: Optional[str] = None
    error: Optional[str] = None
    trace: Optional[str] = None

class StatsResponse(BaseModel):
    running: bool
    trade_speed: int
    depth_speed: int
    total_speed: int
    cassandra_latency_ms: float
    postgres_latency_ms: float
