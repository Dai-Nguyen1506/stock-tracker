import asyncio
import json
import logging
import websockets
from websockets.exceptions import ConnectionClosedError

# Cấu hình logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger(__name__)

# Endpoint dành cho Combined Streams
BASE_URL = "wss://stream.binance.com:9443/stream"

async def stream_market_data(symbols: list, stream_type: str = "all", speed: str = "1000ms"):
    """
    Stream dữ liệu thị trường từ Binance WebSocket.
    
    Args:
        symbols (list): Danh sách các mã giao dịch (vd: ['btcusdt', 'ethusdt']).
        stream_type (str): Loại dữ liệu muốn lấy. Chọn "trade", "depth", hoặc "all".
        speed (str): Tốc độ cập nhật của depth. Chọn "1000ms" hoặc "100ms".
    """
    if not symbols:
        logger.warning("Danh sách symbols trống. Dừng stream.")
        return

    # 1. Tổng hợp danh sách các streams cần Subscribe
    streams_to_subscribe = []
    
    # Xử lý hậu tố tốc độ cho Depth
    depth_suffix = "@depth" if speed == "1000ms" else f"@depth@{speed}"

    if stream_type in ["trade", "all"]:
        streams_to_subscribe.extend([f"{s.lower()}@trade" for s in symbols])
        
    if stream_type in ["depth", "all"]:
        streams_to_subscribe.extend([f"{s.lower()}{depth_suffix}" for s in symbols])

    total_streams = len(streams_to_subscribe)
    
    # 2. Kiểm tra giới hạn 1024 streams / 1 kết nối
    if total_streams > 1024:
        logger.error(f"Vượt quá giới hạn! Bạn đang yêu cầu {total_streams} luồng, nhưng Binance chỉ cho phép tối đa 1024 luồng/kết nối.")
        logger.error("Gợi ý: Hãy giảm số lượng symbols, hoặc chia ra chạy trên nhiều task/kết nối khác nhau.")
        return

    # 3. Mở kết nối và duy trì
    while True:
        try:
            logger.info(f"Đang mở kết nối WebSocket cho {total_streams} luồng (Loại: {stream_type})...")
            
            async with websockets.connect(BASE_URL) as ws:
                logger.info("Kết nối thành công! Bắt đầu gửi lệnh Subscribe...")

                # Băm nhỏ (Chunking) danh sách để gửi dần, tránh lỗi rate limit 5 msg/giây
                chunk_size = 150
                for i in range(0, total_streams, chunk_size):
                    chunk = streams_to_subscribe[i:i + chunk_size]
                    
                    subscribe_msg = {
                        "method": "SUBSCRIBE",
                        "params": chunk,
                        "id": i + 1
                    }
                    
                    await ws.send(json.dumps(subscribe_msg))
                    logger.info(f"Đã đăng ký cụm {i//chunk_size + 1} ({len(chunk)} luồng)")
                    
                    # Ngủ 0.5s giữa các lần gửi lệnh để an toàn tuyệt đối
                    await asyncio.sleep(0.5)
                
                logger.info("Hoàn tất đăng ký. Hệ thống đang lắng nghe dữ liệu...")

                # Vòng lặp nhận dữ liệu liên tục
                while True:
                    msg = await ws.recv()
                    payload = json.loads(msg)
                    
                    # Bỏ qua các tin nhắn rác báo cáo kết quả của lệnh SUBSCRIBE
                    if "result" in payload and payload["result"] is None:
                        continue
                        
                    # Trả về payload hợp lệ
                    # Với endpoint /stream, payload chuẩn sẽ có dạng {"stream": "...", "data": {...}}
                    if "stream" in payload and "data" in payload:
                        yield payload

        except (ConnectionClosedError, ConnectionRefusedError) as e:
            logger.error(f"Mất kết nối mạng: {e}. Đang thử lại sau 5s...")
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            logger.info("Nhận lệnh tắt. Đóng WebSocket an toàn...")
            break
        except Exception as e:
            logger.critical(f"Lỗi hệ thống không xác định: {e}")
            await asyncio.sleep(5)