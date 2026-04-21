# Stock Tracker - Nhánh khám phá dữ liệu với FinnHub

Nhánh này tập trung vào việc kết nối Finnhub để:
- Khám phá dữ liệu thị trường trong notebook.
- Stream dữ liệu giao dịch thời gian thực (real-time) qua WebSocket.
- Chuẩn hóa cấu hình API key thông qua file `.env`.

## 1. Tóm tắt nội dung chính của nhánh

### Mục tiêu
- Thiết lập nền tảng lấy dữ liệu cổ phiếu từ Finnhub cho các bước xử lý/phân tích tiếp theo.
- Tách riêng phần cấu hình và phần stream dữ liệu để dễ tái sử dụng.

### Thành phần chính
- `notebooks/finnhub.ipynb`
	- Notebook để thử nghiệm API, khám phá và trực quan hóa dữ liệu.
- `src/config.py`
	- Đọc biến môi trường từ file `.env`.
	- Cung cấp lớp `Config` và hàm `validate()` để kiểm tra `FINNHUB_API_KEY`.
- `src/streamer.py`
	- Cung cấp async generator `finnhub_streamer(api_key, symbols)`.
	- Tự động subscribe danh sách mã và yield dữ liệu trade khi có bản tin mới.
- `requirements.txt`
	- Danh sách thư viện cần cài cho notebook và module stream.

## 2. Yêu cầu môi trường

- Python: **3.12.3** (đang dùng trong môi trường hiện tại của dự án)
- Khuyến nghị: Python 3.10+ nếu bạn muốn chạy tương thích rộng hơn.
- Tài khoản Finnhub và API key hợp lệ.

## 3. Cài đặt nhanh

### Bước 1: Tạo và kích hoạt môi trường ảo (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Bước 2: Cài dependencies

```powershell
pip install -r requirements.txt
```

### Bước 3: Tạo file `.env` tại thư mục gốc dự án

```env
FINNHUB_API_KEY=your_finnhub_api_key
```

## 4. Hướng dẫn sử dụng

### Cách A: Dùng notebook để khám phá dữ liệu

```powershell
jupyter notebook
```

Sau đó mở file `notebooks/finnhub.ipynb` và chạy lần lượt các cell.

### Cách B: Stream dữ liệu real-time bằng module Python

Ví dụ chạy nhanh:

```python
import asyncio
from src.config import Config
from src.streamer import finnhub_streamer


async def main():
		Config.validate()

		symbols = ["AAPL", "MSFT", "GOOGL"]
		async for trades in finnhub_streamer(Config.FINNHUB_API_KEY, symbols):
				print(trades)


if __name__ == "__main__":
		asyncio.run(main())
```

Lưu đoạn code vào file Python (ví dụ `run_stream.py`) rồi chạy:

```powershell
python run_stream.py
```

## 5. Lỗi thường gặp

- `FINNHUB_API_KEY không tồn tại trong file .env`
	- Kiểm tra file `.env` có đúng tên và đặt tại thư mục gốc dự án.
- Không nhận được dữ liệu trade
	- Kiểm tra API key, kết nối mạng, và ký hiệu mã cổ phiếu đã subscribe.

## 6. Cấu trúc thư mục hiện tại

```text
README.md
requirements.txt
notebooks/
	finnhub.ipynb
src/
	__init__.py
	config.py
	streamer.py
```

## 7. Ghi chú

Nhánh `test/finnhub` là nhánh thử nghiệm/khám phá dữ liệu để chuẩn bị cho các bước phát triển tiếp theo của Stock Tracker (lưu trữ, xử lý, trực quan hóa nâng cao, hoặc tích hợp dashboard).