from fastapi import APIRouter
from schemas.benchmark import PingTestRequest, BenchmarkResponse, StatsResponse
from services.benchmark_service import BenchmarkService
from core.logger import logger

router = APIRouter()
benchmark_service = BenchmarkService()

@router.get("/stats", response_model=StatsResponse)
async def get_stats():
    """
    Retrieves global system ingestion and latency statistics.
    """
    stats = await benchmark_service.get_stats()
    return StatsResponse(**stats) if stats else StatsResponse(
        running=False, trade_speed=0, depth_speed=0, total_speed=0, 
        cassandra_latency_ms=0, postgres_latency_ms=0
    )

@router.post("/test/ping", response_model=BenchmarkResponse)
async def test_ping(request: PingTestRequest):
    """
    Performs a latency test on Cassandra for kline data.
    """
    logger.info(f"Benchmark: Cassandra Ping for {request.symbol}")
    result = await benchmark_service.cassandra_ping(request.symbol, request.interval, request.start_date, request.end_date)
    return BenchmarkResponse(**result)

@router.post("/postgres/copy", response_model=BenchmarkResponse)
async def postgres_copy(request: PingTestRequest):
    """
    Benchmarks copying data from Cassandra to PostgreSQL.
    """
    logger.info(f"Benchmark: Postgres Copy for {request.symbol}")
    result = await benchmark_service.postgres_copy(request.symbol, request.interval, request.start_date, request.end_date)
    if isinstance(result, str):
         return BenchmarkResponse(status=result)
    return BenchmarkResponse(**result)

@router.post("/postgres/ping", response_model=BenchmarkResponse)
async def postgres_ping(request: PingTestRequest):
    """
    Performs a latency test on PostgreSQL for kline data.
    """
    logger.info(f"Benchmark: Postgres Ping for {request.symbol}")
    result = await benchmark_service.postgres_ping(request.symbol, request.interval, request.start_date, request.end_date)
    return BenchmarkResponse(**result)
