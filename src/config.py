import os
from pathlib import Path
from dotenv import load_dotenv

# Xác định đường dẫn gốc của dự án
BASE_DIR = Path(__file__).resolve().parent.parent

# Load biến môi trường từ file .env
load_dotenv(BASE_DIR / '.env')

class Config:
    """Cấu hình chung cho ứng dụng"""
    FINNHUB_API_KEY = os.getenv('FINNHUB_API_KEY')

    @classmethod
    def validate(cls):
        """Kiểm tra xem các cấu hình quan trọng đã có chưa"""
        if not cls.FINNHUB_API_KEY:
            raise ValueError("❌ FINNHUB_API_KEY không tồn tại trong file .env")