import os

def save_data(df, filename):
    # Trỏ ra thư mục data ở cấp cha (ROOT)
    filepath = os.path.join('..', 'data', filename)
    
    # Tạo thư mục data ở ROOT nếu chưa có
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    df.to_csv(filepath, index=False, encoding='utf-8-sig')
    print(f"✅ Data saved to: {os.path.abspath(filepath)}")