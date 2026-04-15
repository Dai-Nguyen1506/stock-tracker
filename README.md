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

## Tệp liên quan

- `quickstart_stock_vietnam.ipynb`: Notebook chính để thử nghiệm và khám phá dữ liệu.
- `api.txt`, `api.demo.txt`: Ghi chú nhanh về API/lệnh gọi thử nghiệm.

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
