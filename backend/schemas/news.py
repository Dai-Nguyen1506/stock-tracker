from pydantic import BaseModel
from typing import List, Optional

class NewsItem(BaseModel):
    timestamp: int
    headline: str
    url: str
    symbol: str

class NewsHistoryResponse(BaseModel):
    data: List[NewsItem]
    year: int
    month: int
    error: Optional[str] = None
