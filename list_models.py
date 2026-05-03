import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)

print("Danh sách các model hỗ trợ tạo văn bản (generateContent):")
print("-" * 50)

try:
    # Lấy danh sách tất cả các models
    for m in genai.list_models():
        # Chỉ in ra những model hỗ trợ text (generateContent)
        if 'generateContent' in m.supported_generation_methods:
            print(m.name)
except Exception as e:
    print("Lỗi khi lấy danh sách:", e)