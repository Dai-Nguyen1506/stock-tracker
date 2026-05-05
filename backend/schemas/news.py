from pydantic import BaseModel
from typing import List, Optional

class NewsItem(BaseModel):
    timestamp: int
    headline: str
    url: str
    symbol: str

class NewsHistoryResponse(BaseModel):
    data: List[NewsItem]
    error: Optional[str] = None
