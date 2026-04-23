from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from groq import AsyncGroq
from core.vector_db import get_news_collection
from core.cassandra import get_session
from datetime import datetime, timezone, timedelta
from typing import List, Optional
import json
import os

router = APIRouter()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
client = AsyncGroq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

class ChatRequest(BaseModel):
    query: str
    symbol: str = None
    interval: str = "1m"

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
    if not client:
        raise HTTPException(status_code=500, detail="Groq API Key is missing")

    full_symbol = req.symbol.upper() if req.symbol else "BTCUSDT"
    base_symbol = full_symbol.replace("USDT", "")
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 1. Lấy Tin tức (RAG)
    collection = get_news_collection()
    context_news = "Không có tin tức mới."
    if collection:
        try:
            # Tìm kiếm theo các biến thể symbol
            possible_syms = [base_symbol, f"{base_symbol}USD", f"{base_symbol}USDT"]
            where_filter = {"symbol": {"$in": possible_syms}}
            
            res = collection.query(query_texts=[req.query], n_results=5, where=where_filter)
            if res['documents'] and res['documents'][0]:
                context_news = "\n".join([f"- {doc}" for doc in res['documents'][0]])
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

CÂU HỎI: {req.query}"""

    # --- Provider 1: Groq ---
    try:
        completion = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=0.2,
            max_tokens=2048
        )
        return ChatResponse(response=completion.choices[0].message.content)
    except Exception as groq_e:
        error_msg = str(groq_e)
        print(f"⚠️ Groq Error: {error_msg}")
        
        # --- Provider 2: Gemini Fallback (Nếu Groq lỗi 403 hoặc lỗi khác) ---
        gemini_key = os.getenv("GEMINI_API_KEY", "")
        if gemini_key:
            print("🔄 Falling back to Gemini...")
            try:
                import httpx
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
                payload = {
                    "contents": [{
                        "parts": [{
                            "text": f"{system_prompt}\n\nUSER QUESTION:\n{user_content}"
                        }]
                    }],
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
            except Exception as gem_e:
                print(f"❌ Gemini Exception: {gem_e}")

        # Nếu cả 2 đều lỗi hoặc không có Gemini Key
        if "403" in error_msg:
            return ChatResponse(response="Lỗi 403 (Access Denied) từ Groq. Điều này thường do IP của bạn bị chặn hoặc giới hạn vùng địa lý. Tôi đã thử chuyển sang Gemini nhưng cũng không thành công. Vui lòng kiểm tra lại API Key hoặc VPN.")
        return ChatResponse(response=f"AI Error: {error_msg}")

