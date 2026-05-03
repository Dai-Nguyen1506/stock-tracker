from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from core.vector_db import get_news_collection
from core.cassandra import get_session
from core.redis_client import get_redis
from datetime import datetime, timezone, timedelta
from typing import List, Optional
import json
import os

router = APIRouter()
# Xóa Groq vì gặp lỗi 403, chỉ sử dụng Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

class ChatRequest(BaseModel):
    query: str
    symbol: str = None
    interval: str = "1m"
    history: List[dict] = []

class ChatResponse(BaseModel):
    response: str

async def get_recent_klines(symbol: str, interval="1m", limit=5):
    """Lấy dữ liệu nến từ Cassandra với logic fallback mạnh mẽ"""
    try:
        session = await get_session()
        dt_now = datetime.now(timezone.utc)
        
        # Thử lấy dữ liệu trong 3 ngày gần nhất (để chắc chắn có data nếu thị trường nghỉ hoặc lag)
        klines = []
        cql = "SELECT timestamp, open, high, low, close, volume FROM market_data.klines WHERE symbol=? AND interval=? AND date_bucket=? LIMIT ?"
        prepared = await session.create_prepared(cql)

        for i in range(3):
            date_bucket = (dt_now - timedelta(days=i)).date()
            bound = prepared.bind()
            bound.bind_list([symbol, interval, date_bucket, limit])
            rows = await session.execute(bound)
            
            for r in rows:
                ts = r.timestamp
                if isinstance(ts, int):
                    # Acsylla often returns timestamp as ms integer
                    ts = datetime.fromtimestamp(ts / 1000.0, timezone.utc)
                klines.append(f"T: {ts.strftime('%H:%M')}, C: {r.close}, V: {r.volume}")
            
            if len(klines) >= limit:
                break
                
        if not klines:
            return "Không tìm thấy dữ liệu giá gần đây trong Database."
            
        return "\n".join(klines[:limit])
    except Exception as e:
        print(f"❌ Error fetching klines: {e}")
        return f"Lỗi truy vấn giá: {str(e)}"

def load_system_prompt():
    try:
        prompt_path = os.path.join(os.path.dirname(__file__), "..", "core", "chatbot_prompt.md")
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    except:
        return "You are a professional financial AI assistant. Use provided market data and news to help users."

@router.post("")
async def chat_with_bot(req: ChatRequest):

    full_symbol = req.symbol.upper() if req.symbol else "BTCUSDT"
    
    # Simple symbol extraction from query
    words = req.query.upper().replace(",", " ").replace("?", " ").replace(".", " ").split()
    
    # Cố gắng tìm một mã giao dịch trong câu hỏi
    redis = get_redis()
    symbol_from_query = False
    if redis:
        try:
            cached_symbols_json = await redis.get("market_symbols")
            if cached_symbols_json:
                data = json.loads(cached_symbols_json)
                all_bases = [item["base"].upper() for item in data.get("priority_list", [])] + [item["base"].upper() for item in data.get("remainder_list", [])]
                
                for w in words:
                    # Ưu tiên khớp chính xác (ví dụ: 'VIC' thay vì 'VICTORY')
                    if w in all_bases:
                        full_symbol = f"{w}USDT"
                        symbol_from_query = True
                        break
                    # Khớp nếu nó là một phần của mã đầy đủ (ví dụ: BTC trong BTCUSDT)
                    if not symbol_from_query:
                        for base in all_bases:
                             if w == f"{base}USDT":
                                full_symbol = w
                                symbol_from_query = True
                                break
                    if symbol_from_query:
                        break
        except Exception as e:
            print(f"⚠️ Warning: Symbol detection failed: {e}")
            pass

    base_symbol = full_symbol.replace("USDT", "")
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 1. Lấy Tin tức (RAG)
    collection = get_news_collection()
    context_news = "Không có tin tức mới."
    if collection:
        try:
            count = collection.count()
            if count > 0:
                # Lấy nhiều kết quả hơn một chút để lọc theo thời gian
                n = 5
                fetch_n = 15
                query_params = {"query_texts": [req.query], "n_results": min(fetch_n, count)}
                if symbol_from_query:
                    query_params["where"] = {"symbol": base_symbol}

                res = collection.query(**query_params)
                
                if res['documents'] and res['documents'][0]:
                    # Gộp tài liệu và metadata để sắp xếp
                    combined = []
                    for doc, meta in zip(res['documents'][0], res['metadatas'][0]):
                        combined.append({"doc": doc, "meta": meta, "ts": meta.get("timestamp", 0)})
                    
                    # Sắp xếp theo timestamp giảm dần (mới nhất lên đầu)
                    combined.sort(key=lambda x: x["ts"], reverse=True)
                    
                    news_list = []
                    for item in combined[:n]:
                        ts_ms = item["ts"]
                        doc = item["doc"]
                        if ts_ms:
                            # Chuyển đổi timestamp sang giờ Việt Nam (UTC+7)
                            dt = datetime.fromtimestamp(ts_ms / 1000.0, timezone.utc) + timedelta(hours=7)
                            time_str = dt.strftime("%H:%M %d/%m/%Y")
                            news_list.append(f"- [Lúc {time_str}] {doc}")
                        else:
                            news_list.append(f"- {doc}")
                    context_news = "\n".join(news_list)
        except Exception as e: 
            print(f"⚠️ Warning: RAG query failed: {e}")
            pass

    # 2. Lấy Giá (Cassandra)
    price_context = await get_recent_klines(full_symbol, req.interval)

    # 3. AI Generate
    system_prompt = load_system_prompt()
    user_content = f"""MÃ: {full_symbol}
HÔM NAY:
{current_time}

GIÁ GẦN ĐÂY:
{price_context}

TIN TỨC GẦN ĐÂY:
{context_news}

CÂU HỎI MỚI NHẤT: {req.query}"""

    # Build messages array including history
    messages = [{"role": "system", "content": system_prompt}]
    for msg in req.history[:-1]: # exclude the last user msg because we inject it with context
        messages.append({"role": msg.get("role", "user"), "content": msg.get("text", "")})
    messages.append({"role": "user", "content": user_content})

    # --- Provider: Gemini ---
    if not GEMINI_API_KEY:
        return ChatResponse(response="Lỗi hệ thống: Chưa cấu hình GEMINI_API_KEY. Vui lòng kiểm tra lại cấu hình môi trường.")
        
    try:
        import httpx
        
        # Danh sách model theo thứ tự: 1. Quota trâu nhất -> 2. Thông minh, Quota cao
        MODELS = [
            "gemini-3.1-flash-lite-preview", 
            "gemini-3.1-flash-preview",
            "gemini-2.5-flash" # Chốt chặn cuối cùng
        ]
        
        # Format history chuẩn cho Gemini (chỉ user/model)
        gemini_contents = []
        for msg in req.history[:-1]:
            r = "user" if msg.get("role") == "user" else "model"
            gemini_contents.append({"role": r, "parts": [{"text": msg.get("text", "")}]})
            
        gemini_contents.append({"role": "user", "parts": [{"text": user_content}]})
        
        payload = {
            # Sử dụng system_instruction chuẩn của API thay vì fake history
            "system_instruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": gemini_contents,
            "generationConfig": {
                "temperature": 0.2, # Giữ ở mức thấp để output tài chính có độ chính xác cao
                "maxOutputTokens": 2048
            }
        }
        
        async with httpx.AsyncClient() as h_client:
            for model_name in MODELS:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
                
                res = await h_client.post(url, json=payload, timeout=30.0)
                res_data = res.json()
                
                if res.status_code == 200:
                    ai_text = res_data['candidates'][0]['content']['parts'][0]['text']
                    return ChatResponse(response=ai_text)
                    
                elif res.status_code == 429:
                    print(f"⚠️ [Fallback] Model {model_name} hết Quota. Đang chuyển sang model tiếp theo...")
                    continue # Bỏ qua vòng lặp hiện tại, gọi model tiếp theo trong danh sách
                    
                else:
                    gemini_error = res_data.get('error', {}).get('message', 'Unknown Gemini Error')
                    print(f"❌ Gemini Error ({model_name}): {gemini_error}")
                    return ChatResponse(response=f"Lỗi API từ {model_name}: {gemini_error}")
            
            # Nếu chạy hết vòng lặp for mà code vẫn đến được đây -> Tất cả model đều hết Quota hoặc tèo
            print("🚨 Cảnh báo: Tất cả các model dự phòng đều đã hết Quota!")
            return ChatResponse(response="Hệ thống đang xử lý quá nhiều yêu cầu thị trường. Vui lòng thử lại sau khoảng 1 phút nhé.")
                
    except Exception as e:
        print(f"❌ Exception in Chatbot: {e}")
        return ChatResponse(response=f"AI Error: {str(e)}")

