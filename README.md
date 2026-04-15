# Stock Tracker - Nhánh Khám Phá Dữ Liệu Với vnstock

## Mục tiêu nhánh

Nhánh này chỉ phục vụ một mục tiêu duy nhất:

=> Khám phá dữ liệu thị trường chứng khoán Việt Nam bằng thư viện `vnstock`.


## Phạm vi thực hiện
Trong nhánh này, ưu tiên các hoạt động:

- Thử nghiệm cách lấy dữ liệu từ `vnstock`.
- Kiểm tra cấu trúc dữ liệu trả về (cột, kiểu dữ liệu, độ đầy đủ).
- Khám phá dữ liệu bằng notebook.
- Thử nghiệm các truy vấn/bộ lọc cơ bản để hiểu dữ liệu.

Không nằm trong phạm vi nhánh:

- Xây dựng backend hoàn chỉnh.
- Viết API public ổn định.
- Chuẩn hóa toàn bộ pipeline production.

## Environment setup

Phần này giúp bạn setup môi trường từ đầu trước khi chạy notebook.

### 1) Yêu cầu hệ thống

- Python 3.10+ (khuyến nghị 3.11)
- pip mới (đi kèm Python)
- VS Code + extension Jupyter (khuyến nghị)

Kiểm tra nhanh phiên bản:

```powershell
python --version
pip --version
```

### 2) Tạo và kích hoạt môi trường ảo

Từ thư mục gốc dự án:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Nếu bị chặn script trên PowerShell, chạy tạm lệnh sau rồi kích hoạt lại:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### 3) Cài dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4) Cấu hình biến môi trường

Sao chép file mẫu và điền API key:

```powershell
Copy-Item .env.example .env
```

Mở file `.env` và chỉnh giá trị  (nếu không có thì bỏ qua):

```env
VNSTOCK_API_KEY=YOUR_REAL_API_KEY
```

Ghi chú:
- Notebook sẽ đọc `VNSTOCK_API_KEY` từ `.env`.
- Không commit file `.env` (đã được ignore trong `.gitignore`).

### 5) Chạy notebook

Khởi động Jupyter:

```powershell
jupyter notebook
```

Hoặc nếu dùng VS Code:
- Mở notebook trong thư mục `notebooks/`.
- Chọn kernel Python từ `.venv`.
- Chạy từ cell đầu tiên theo thứ tự.

Ví dụ notebook nên chạy trước:
- `notebooks/quickstart_stock_vietnam.ipynb`
- `notebooks/vnstock.ipynb`

### 6) Kiểm tra nhanh sau setup

Chạy lệnh test import:

```powershell
python -c "import vnstock, pandas, dotenv; print('OK: environment ready')"
```

## Tệp liên quan

- `quickstart_stock_vietnam.ipynb`: Notebook chính để thử nghiệm và khám phá dữ liệu.
- `.env`: Lưu biến môi trường cục bộ (ví dụ `VNSTOCK_API_KEY`).
- `.env.example`: Mẫu cấu hình để chia sẻ trong nhóm (không chứa key thật).

## Cách sử dụng nhánh

1. Kích hoạt môi trường ảo `.venv`.
2. Mở notebook `quickstart_stock_vietnam.ipynb`.
3. Chạy từng cell để lấy dữ liệu và quan sát kết quả.
4. Điều chỉnh tham số mã cổ phiếu, khoảng thời gian và tần suất để so sánh.

## Kết quả mong đợi

Sau khi làm việc với nhánh này, bạn có thể:

- Hiểu cách sử dụng `vnstock` để lấy dữ liệu cần thiết.
- Nắm được đặc điểm dữ liệu trước khi đi tiếp sang bước xử lý/phân tích sau.
- Có notebook mẫu để tái sử dụng cho các nhánh tiếp theo.

## Ghi chú

Nếu sau này mở rộng sang xây dựng hệ thống hoàn chỉnh, nên tạo nhánh mới (ví dụ: `feature/pipeline` hoặc `feature/api`) để tách biệt với nhánh khám phá dữ liệu.
