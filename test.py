import os
from dotenv import load_dotenv
import google.generativeai as genai

# Tải các biến môi trường từ file .env
load_dotenv()

# Lấy API key từ biến môi trường
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("Lỗi: Không tìm thấy GEMINI_API_KEY trong file .env. Vui lòng kiểm tra lại!")
else:
    try:
        # Cấu hình API key cho thư viện
        genai.configure(api_key=api_key)

        # Khởi tạo model (sử dụng gemini-1.5-flash cho tác vụ text cơ bản và nhanh)
        model = genai.GenerativeModel('gemini-3.1-flash-lite-preview')

        print("Đang gửi yêu cầu kiểm tra đến Gemini API...")
        
        # Gửi một prompt thử nghiệm
        response = model.generate_content("Xin chào, nay thời tiết thế nào?")

        # In kết quả nếu thành công
        print("\n✅ KẾT NỐI THÀNH CÔNG! Phản hồi từ Gemini:")
        print("-" * 50)
        print(response.text.strip())
        print("-" * 50)

    except Exception as e:
        # In ra lỗi chi tiết nếu có vấn đề (sai key, hết quota, lỗi mạng, v.v.)
        print("\n❌ Đã xảy ra lỗi trong quá trình gọi API:")
        print(e)