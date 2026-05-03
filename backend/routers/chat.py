from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from groq import AsyncGroq
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
    
    # Try to find a symbol in the query (e.g. BTC, ETH, SOL)
    redis = get_redis()
    if redis:
        try:
            cached_symbols_json = await redis.get("market_symbols")
            if cached_symbols_json:
                data = json.loads(cached_symbols_json)
                all_bases = [item["base"].upper() for item in data.get("priority_list", [])] + [item["base"].upper() for item in data.get("remainder_list", [])]
                found = False
                for w in words:
                    for base in all_bases:
                        if w == base or w == f"{base}USDT":
                            full_symbol = f"{base}USDT"
                            found = True
                            break
                    if found:
                        break
        except Exception:
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
                n = min(5, count)
                # Trả lại bộ lọc where để chỉ lấy tin tức đúng mã giao dịch
                res = collection.query(query_texts=[req.query], n_results=n, where={"symbol": base_symbol})
                if res['documents'] and res['documents'][0]:
                    news_list = []
                    for doc, meta in zip(res['documents'][0], res['metadatas'][0]):
                        ts_ms = meta.get("timestamp", 0)
                        if ts_ms:
                            # Chuyển đổi timestamp sang giờ Việt Nam (UTC+7)
                            dt = datetime.fromtimestamp(ts_ms / 1000.0, timezone.utc) + timedelta(hours=7)
                            time_str = dt.strftime("%H:%M %d/%m/%Y")
                            news_list.append(f"- [Lúc {time_str}] {doc}")
                        else:
                            news_list.append(f"- {doc}")
                    context_news = "\n".join(news_list)
        except: pass

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
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
        
        # Format history for Gemini (user/model)
        gemini_contents = []
        # System prompt
        gemini_contents.append({"role": "user", "parts": [{"text": system_prompt}]})
        gemini_contents.append({"role": "model", "parts": [{"text": "Đã hiểu."}]})
        
        for msg in req.history[:-1]:
            r = "user" if msg.get("role") == "user" else "model"
            gemini_contents.append({"role": r, "parts": [{"text": msg.get("text", "")}]})
        gemini_contents.append({"role": "user", "parts": [{"text": user_content}]})
        
        payload = {
            "contents": gemini_contents,
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 2048
            }
        }
        async with httpx.AsyncClient() as h_client:
            res = await h_client.post(url, json=payload, timeout=30.0)
            res_data = res.json()
            
            if res.status_code == 200:
                ai_text = res_data['candidates'][0]['content']['parts'][0]['text']
                return ChatResponse(response=ai_text)
            else:
                gemini_error = res_data.get('error', {}).get('message', 'Unknown Gemini Error')
                print(f"❌ Gemini Error: {gemini_error}")
                return ChatResponse(response=f"Lỗi API: {gemini_error}")
                
    except Exception as e:
        print(f"❌ Exception in Chatbot: {e}")
        return ChatResponse(response=f"AI Error: {str(e)}")

