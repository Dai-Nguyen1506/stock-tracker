import requests
import pandas as pd

def validate_domains(df_raw):
    candidate_domains = ["https://vietstock.vn", "https://cafef.vn"]
    headers = {'User-Agent': 'Mozilla/5.0...'}
    
    verified_data = []
    total_links = len(df_raw)
    
    print(f"🧪 Đang xác thực {total_links} đường link...")

    for i, row in df_raw.iterrows():
        original_url = row['url']
        final_url = original_url # Mặc định giữ nguyên nếu không tìm thấy domain
        
        for domain in candidate_domains:
            test_url = f"{domain}{original_url}"
            try:
                # Check HEAD cực nhanh
                r = requests.head(test_url, headers=headers, timeout=2)
                if r.status_code == 200:
                    final_url = test_url
                    break
            except:
                continue
        
        verified_data.append({
            "symbol": row['symbol'],
            "valid_url": final_url,
            "title": row['title']
        })
        
        if (i+1) % 50 == 0:
            print(f"Đã xử lý: {i+1}/{total_links}")

    return pd.DataFrame(verified_data)