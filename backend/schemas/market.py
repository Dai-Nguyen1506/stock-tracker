from pydantic import BaseModel
from typing import List, Optional

class KlineItem(BaseModel):
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float

class HistoryResponse(BaseModel):
    symbol: str
    interval: str
    data: List[KlineItem]

class SymbolListResponse(BaseModel):
    priority: List[str]
    remainder: List[str]
