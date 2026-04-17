import os
import pandas as pd

def load_data(filename):
    # Đường dẫn trỏ từ notebooks/ ra ROOT rồi vào data/
    filepath = os.path.join('..', 'data', filename)
    
    if os.path.exists(filepath):
        return pd.read_csv(filepath)
    else:
        print(f"❌ Không tìm thấy file: {filepath}")
        return None