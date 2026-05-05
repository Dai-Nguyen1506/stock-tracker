from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
from core.redis_client import get_redis
from core.logger import logger

router = APIRouter()

class ConnectionManager:
    """
    Manages active WebSocket connections.
    """
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """
        Accepts a new WebSocket connection and adds it to the list of active connections.
        """
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        """
        Removes a WebSocket connection from the list of active connections.
        """
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

manager = ConnectionManager()

@router.websocket("/live")
async def websocket_global_endpoint(websocket: WebSocket):
    """
    Global WebSocket endpoint for live news and stats updates.
    """
    await manager.connect(websocket)
    redis_client = get_redis()
    pubsub = redis_client.pubsub()
    await pubsub.subscribe("live:news", "live:stats")
    
    async def redis_listener():
        try:
            async for message in pubsub.listen():
                if message['type'] == 'message':
                    await websocket.send_text(message['data'])
        except Exception as e:
            logger.error(f"[WS] Global Redis listener error: {e}")

    listener_task = asyncio.create_task(redis_listener())

    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        listener_task.cancel()
        await pubsub.unsubscribe()
    except Exception:
        manager.disconnect(websocket)
        listener_task.cancel()
        await pubsub.unsubscribe()

@router.websocket("/live/{symbol}")
async def websocket_endpoint(websocket: WebSocket, symbol: str):
    """
    Symbol-specific WebSocket endpoint for live kline and news updates.
    """
    await manager.connect(websocket)
    redis_client = get_redis()
    pubsub = redis_client.pubsub()
    
    symbol = symbol.upper()
    await pubsub.subscribe(f"live:klines:{symbol}", "live:news")
    
    async def redis_listener():
        try:
            async for message in pubsub.listen():
                if message['type'] == 'message':
                    await websocket.send_text(message['data'])
        except Exception as e:
            logger.error(f"[WS] Redis listener error for {symbol}: {e}")

    listener_task = asyncio.create_task(redis_listener())

    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        listener_task.cancel()
        await pubsub.unsubscribe()
    except Exception:
        manager.disconnect(websocket)
        listener_task.cancel()
        await pubsub.unsubscribe()
