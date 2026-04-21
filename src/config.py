import os
from pathlib import Path
from dotenv import load_dotenv

# Xác định đường dẫn gốc của dự án
BASE_DIR = Path(__file__).resolve().parent.parent

# Load biến môi trường từ file .env
load_dotenv(BASE_DIR / '.env')

class Config:
    """Cấu hình chung cho ứng dụng"""
    APCA_API_KEY_ID = os.getenv('APCA_API_KEY_ID')
    APCA_API_SECRET_KEY = os.getenv('APCA_API_SECRET_KEY')

    @classmethod
    def validate(cls):
        """Kiểm tra xem các cấu hình quan trọng đã có chưa"""
        if not cls.APCA_API_KEY_ID:
            raise ValueError("❌ APCA_API_KEY_ID không tồn tại trong file .env")
        if not cls.APCA_API_SECRET_KEY:
            raise ValueError("❌ APCA_API_SECRET_KEY không tồn tại trong file .env")