from fastapi import APIRouter, Depends
from core.cassandra import get_session

router = APIRouter()

@router.get("/")
async def list_stocks():
    """Placeholder — sẽ bổ sung ở Giai đoạn 2"""
    return {"message": "Stocks API ready", "stocks": []}

@router.get("/{symbol}/latest")
async def get_latest(symbol: str, session=Depends(get_session)):
    stmt = await session.create_prepared(
        "SELECT * FROM vn_ohlcv WHERE symbol=? AND date_bucket=toDate(now()) LIMIT 1"
    )
    bound = stmt.bind()
    bound.bind_list([symbol.upper()])
    result = await session.execute(bound)
    rows = await result.all()
    return {"symbol": symbol, "data": rows[0] if rows else None}