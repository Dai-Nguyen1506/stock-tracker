import time
import pandas as pd
from vnstock import Company

def fetch_all_raw_links(symbols):
    raw_news_list = []
    total = len(symbols)
    
    print(f"🚀 Bắt đầu lấy link thô cho {total} mã...")
    
    for i, symbol in enumerate(symbols):
        start_time = time.time()
        try:
            # Chỉ gọi API để lấy link từ KBS
            cp = Company(symbol=symbol, source='KBS')
            df = cp.news()
            
            if not df.empty:
                # Thêm cột symbol để biết link này của mã nào
                df['symbol'] = symbol
                raw_news_list.append(df[['symbol', 'title', 'url', 'publish_time']])
                
            print(f"[{i+1}/{total}] Lấy xong: {symbol}")
            
        except Exception as e:
            print(f"⚠️ Lỗi tại {symbol}: {e}")

        # Kiểm soát tốc độ: Đảm bảo không quá 60 req/phút
        elapsed = time.time() - start_time
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
            
    # Gộp tất cả thành một DataFrame duy nhất
    if raw_news_list:
        full_raw_df = pd.concat(raw_news_list, ignore_index=True)
        return full_raw_df
    return pd.DataFrame()
