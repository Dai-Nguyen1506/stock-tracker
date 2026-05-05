import os
import json
from datetime import datetime, timezone, timedelta
import google.generativeai as genai
from core.cassandra import get_session
from core.redis_client import get_redis
from core.vector_db import get_news_collection
from core.logger import logger
from core.config import settings

class ChatService:
    """
    Service for handling AI-powered financial chat interactions using Gemini.
    """
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        if self.api_key:
            genai.configure(api_key=self.api_key)
        
        self.models = [
            "gemini-3.1-flash-lite-preview", 
            "gemini-3.1-flash-preview",
            "gemini-2.5-flash"
        ]

    def _load_system_prompt(self) -> str:
        """
        Loads the system prompt from the markdown file.
        """
        try:
            prompt_path = os.path.join(os.path.dirname(__file__), "..", "core", "chatbot_prompt.md")
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return "You are a professional financial AI assistant. Use provided market data and news to help users."

    async def _get_recent_klines(self, symbol: str, interval: str = "1m", limit: int = 5) -> str:
        """
        Retrieves recent kline data for the given symbol to provide context to the AI.
        """
        try:
            session = await get_session()
            dt_now = datetime.now(timezone.utc)
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
                        ts = datetime.fromtimestamp(ts / 1000.0, timezone.utc)
                    klines.append(f"T: {ts.strftime('%H:%M')}, C: {r.close}, V: {r.volume}")
                
                if len(klines) >= limit:
                    break
                    
            if not klines:
                return "Recent price data not found in database."
            return "\n".join(klines[:limit])
        except Exception as e:
            logger.error(f"Error fetching klines for chatbot: {e}")
            return f"Price query error: {str(e)}"

    async def chat(self, query: str, symbol: str = None, interval: str = "1m", history: list = []) -> str:
        """
        Processes a user query by combining price data, news context, and AI generation.
        """
        full_symbol = symbol.upper() if symbol else "BTCUSDT"
        
        words = query.upper().replace(",", " ").replace("?", " ").replace(".", " ").split()
        redis = get_redis()
        symbol_from_query = False
        if redis:
            try:
                cached_symbols_json = await redis.get("market_symbols")
                if cached_symbols_json:
                    data = json.loads(cached_symbols_json)
                    all_bases = [item["base"].upper() for item in data.get("priority_list", [])] + [item["base"].upper() for item in data.get("remainder_list", [])]
                    for w in words:
                        if w in all_bases:
                            full_symbol = f"{w}USDT"
                            symbol_from_query = True
                            break
                        if not symbol_from_query:
                            for base in all_bases:
                                 if w == f"{base}USDT":
                                    full_symbol = w
                                    symbol_from_query = True
                                    break
                        if symbol_from_query:
                            break
            except Exception as e:
                logger.warning(f"Symbol detection failed: {e}")

        base_symbol = full_symbol.replace("USDT", "")
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        collection = get_news_collection()
        context_news = "No new news found."
        if collection:
            try:
                count = collection.count()
                if count > 0:
                    fetch_n = 15
                    query_params = {"query_texts": [query], "n_results": min(fetch_n, count)}
                    if symbol_from_query:
                        query_params["where"] = {"symbol": base_symbol}

                    res = collection.query(**query_params)
                    if res['documents'] and res['documents'][0]:
                        combined = []
                        for doc, meta in zip(res['documents'][0], res['metadatas'][0]):
                            combined.append({"doc": doc, "meta": meta, "ts": meta.get("timestamp", 0)})
                        combined.sort(key=lambda x: x["ts"], reverse=True)
                        
                        news_list = []
                        for item in combined[:5]:
                            ts_ms = item["ts"]
                            doc = item["doc"]
                            if ts_ms:
                                dt = datetime.fromtimestamp(ts_ms / 1000.0, timezone.utc) + timedelta(hours=7)
                                time_str = dt.strftime("%H:%M %d/%m/%Y")
                                news_list.append(f"- [At {time_str}] {doc}")
                            else:
                                news_list.append(f"- {doc}")
                        context_news = "\n".join(news_list)
            except Exception as e: 
                logger.warning(f"RAG query failed: {e}")

        price_context = await self._get_recent_klines(full_symbol, interval)

        system_prompt = self._load_system_prompt()
        user_content = f"""SYMBOL: {full_symbol}
CURRENT TIME: {current_time}
RECENT PRICES:
{price_context}
RECENT NEWS:
{context_news}
USER QUERY: {query}"""

        contents = []
        for msg in history[:-1]:
            role = "user" if msg.get("role") == "user" else "model"
            contents.append({"role": role, "parts": [msg.get("text", "")]})
        contents.append({"role": "user", "parts": [user_content]})

        if not self.api_key:
            return "System error: GEMINI_API_KEY is not configured."

        for model_name in self.models:
            try:
                model = genai.GenerativeModel(
                    model_name=model_name,
                    system_instruction=system_prompt
                )
                response = await model.generate_content_async(
                    contents=contents,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.2,
                        max_output_tokens=2048
                    )
                )
                return response.text
            except Exception as e:
                if "429" in str(e):
                    logger.warning(f"Model {model_name} quota exceeded, trying next...")
                    continue
                logger.error(f"Error with model {model_name}: {e}")
                return f"AI Error from {model_name}: {str(e)}"
        
        return "The system is currently overwhelmed. Please try again later."
