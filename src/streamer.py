import asyncio
import websockets
import json
import logging

# Cấu hình logging để dễ theo dõi lỗi
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def finnhub_streamer(api_key: str, symbols: list):
    """
    Module bất đồng bộ để stream dữ liệu từ Finnhub.
    Sử dụng yield để trả về kết quả ngay khi có dữ liệu mới.
    """
    uri = f"wss://ws.finnhub.io?token={api_key}"
    
    try:
        async with websockets.connect(uri) as websocket:
            # 1. Đăng ký (Subscribe) các mã cổ phiếu
            for symbol in symbols:
                subscribe_msg = json.dumps({"type": "subscribe", "symbol": symbol})
                await websocket.send(subscribe_msg)
                logger.info(f"Subscribed to {symbol}")

            # 2. Vòng lặp nhận dữ liệu liên tục
            async for message in websocket:
                data = json.loads(message)
                
                # Kiểm tra nếu là dữ liệu giao dịch (trade) thì mới trả về
                if data.get('type') == 'trade':
                    # Trả về từng kết quả cho phía gọi hàm xử lý
                    yield data['data']
                elif data.get('type') == 'ping':
                    logger.debug("Received ping from server")
                else:
                    logger.info(f"Other message: {data}")

    except websockets.exceptions.ConnectionClosed as e:
        logger.error(f"Kết nối bị đóng: {e}")
    except Exception as e:
        logger.error(f"Lỗi không xác định: {e}")