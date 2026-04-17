import asyncio
import websockets
import json
import logging

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def twelvedata_streamer(api_key: str, symbols: list):
    """
    Module bất đồng bộ để stream dữ liệu từ Twelve Data.
    Sử dụng yield để trả về kết quả ngay khi có dữ liệu mới.
    """
    # Endpoint WebSocket của Twelve Data cho real-time price quotes
    uri = f"wss://ws.twelvedata.com/v1/quotes/price?apikey={api_key}"
    
    try:
        async with websockets.connect(uri) as websocket:
            # 1. Đăng ký (Subscribe) các mã cổ phiếu/crypto
            # Twelve Data yêu cầu danh sách symbols dưới dạng chuỗi, phân tách bằng dấu phẩy
            symbols_str = ",".join(symbols)
            subscribe_msg = json.dumps({
                "action": "subscribe",
                "params": {
                    "symbols": symbols_str
                }
            })
            await websocket.send(subscribe_msg)
            logger.info(f"Đã gửi yêu cầu subscribe cho: {symbols_str}")

            # 2. Vòng lặp nhận dữ liệu liên tục
            async for message in websocket:
                data = json.loads(message)
                
                # Twelve Data phân loại message dựa trên trường 'event'
                event_type = data.get('event')
                
                if event_type == 'price':
                    # Trả về dữ liệu giá (bao gồm symbol, price, timestamp, v.v.)
                    yield data
                
                elif event_type == 'subscribe-status':
                    # Xác nhận từ server về việc subscribe thành công hay thất bại
                    logger.info(f"Trạng thái đăng ký: {data}")
                
                elif event_type == 'heartbeat':
                    # Server đôi khi gửi heartbeat để giữ kết nối
                    logger.debug("Received heartbeat from Twelve Data")
                
                elif data.get('status') == 'error':
                    # Xử lý các lỗi từ phía server (ví dụ: sai API key, vớt rate limit)
                    logger.error(f"Lỗi từ server: {data.get('message')}")
                
                else:
                    logger.info(f"Message khác: {data}")

    except websockets.exceptions.ConnectionClosed as e:
        logger.error(f"Kết nối bị đóng: {e}")
    except Exception as e:
        logger.error(f"Lỗi không xác định: {e}")