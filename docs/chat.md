Viewed discovery.py:1-33
Ran command: `& C:/Users/YOGA/.pyenv/pyenv-win/versions/3.12.3/python.exe c:/Users/YOGA/Desktop/06_SQL_v2/project/stock-tracker/backend/ingestion/discovery.py`

Câu trả lời nằm ở chính dòng log mà bạn nhận được khi chạy script:

**`Cảnh báo: Chưa cấu hình ALPACA_API_KEY/SECRET_KEY. Trả về mảng rỗng.`**

### Giải thích chi tiết:
Trong file `discovery.py`, tại dòng 99-101, có một đoạn code "chống cháy" như sau:

```python
# Nếu Alpaca không lấy được (do chưa có Key) thì tạo danh sách giả (mock) để test
if not alpaca_symbols:
    alpaca_symbols = ["BTC/USD", "ETH/USD", "SOL/USD"]
```

Vì bạn đang chạy script ở môi trường terminal bên ngoài (hoặc chưa truyền API Key vào file `.env` đúng cách), Alpaca không trả về danh sách thật. Khi đó:
1.  Script tự tạo ra 3 mã: `BTC`, `ETH`, `SOL`.
2.  Nó so sánh với 432 mã của Binance.
3.  Kết quả là chỉ có **3 mã này khớp** (Priority), còn lại 429 mã kia bị coi là "Chỉ có ở Binance" (Remainder).

### Cách để lấy đầy đủ (khoảng 30-40 mã Priority):
Bạn cần đảm bảo file `.env` trong thư mục `backend/` có đầy đủ 2 dòng này:
```env
ALPACA_API_KEY_ID=your_key_here
ALPACA_API_SECRET_KEY=your_secret_here
```

**Lưu ý quan trọng**: Khi bạn chạy bằng lệnh `python backend/ingestion/discovery.py` trực tiếp trên máy, nó có thể không đọc được file `.env`. Bạn nên chạy trong Docker (vì Docker đã nạp file `.env`) để thấy danh sách Priority đầy đủ nhất:

```powershell
docker compose exec ingestion-alpaca python ingestion/discovery.py
```

Nếu bạn chạy lệnh Docker trên, bạn sẽ thấy con số Priority tăng lên khoảng **30-50 mã** (tùy vào những mã nào Alpaca đang cho phép giao dịch tại thời điểm đó)._
