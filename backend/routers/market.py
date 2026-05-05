from fastapi import APIRouter, Query
from schemas.market import HistoryResponse, SymbolListResponse, KlineItem
from services.market_service import MarketService
from core.logger import logger

router = APIRouter()
market_service = MarketService()

@router.get("/symbols", response_model=SymbolListResponse)
async def get_symbols():
    """
    Retrieves the list of available market symbols.
    """
    return await market_service.get_symbols()

@router.get("/history", response_model=HistoryResponse)
async def get_history(
    symbol: str = Query(..., description="Trading symbol, e.g., BTCUSDT"),
    interval: str = Query("1m", description="Candle interval"),
    limit: int = Query(500, le=2000, description="Number of candles to retrieve"),
    before_ts: int = Query(None, description="Retrieve data before this timestamp")
):
    """
    Retrieves historical kline data for a specific symbol and interval.
    """
    logger.info(f"[API] History call: {symbol} ({interval})")
    results = await market_service.get_history(symbol, interval, limit, before_ts)
    
    return HistoryResponse(
        symbol=symbol,
        interval=interval,
        data=[KlineItem(**item) for item in results]
    )
