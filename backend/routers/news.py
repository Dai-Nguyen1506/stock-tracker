from fastapi import APIRouter, Query
from schemas.news import NewsHistoryResponse, NewsItem
from services.news_service import NewsService
from core.logger import logger

router = APIRouter()
news_service = NewsService()

@router.get("/history", response_model=NewsHistoryResponse)
async def get_news_history(
    symbol: str = Query(..., description="Base symbol, e.g., BTC"),
    limit: int = Query(20, le=100),
    before_ts: int = Query(None),
    year: int = Query(None, description="Year of news"),
    month: int = Query(None, description="Month of news")
):
    """
    Retrieves historical news items for a specific symbol.
    """
    logger.info(f"News History API call: {symbol}")
    results, year_val, month_val = await news_service.get_news_history(symbol, limit, before_ts, year, month)
    return NewsHistoryResponse(
        data=[NewsItem(**item) for item in results],
        year=year_val,
        month=month_val
    )
