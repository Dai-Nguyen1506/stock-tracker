from fastapi import APIRouter
from schemas.chat import ChatRequest, ChatResponse
from services.chat_service import ChatService
from core.logger import logger

router = APIRouter()
chat_service = ChatService()

@router.post("", response_model=ChatResponse)
async def chat_with_bot(req: ChatRequest):
    logger.info(f"🤖 [Chat] Request received for {req.symbol or 'unknown'}")
    ai_response = await chat_service.chat(
        query=req.query,
        symbol=req.symbol,
        interval=req.interval,
        history=req.history
    )
    return ChatResponse(response=ai_response)
