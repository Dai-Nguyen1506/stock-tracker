from pydantic import BaseModel
from typing import List, Optional

class ChatRequest(BaseModel):
    query: str
    symbol: Optional[str] = None
    interval: str = "1m"
    history: List[dict] = []

class ChatResponse(BaseModel):
    response: str
