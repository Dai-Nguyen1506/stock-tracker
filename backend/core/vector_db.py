import chromadb
from chromadb.config import Settings
import logging

logger = logging.getLogger(__name__)
_chroma_client = None

def get_chroma_client():
    global _chroma_client
    if _chroma_client is None:
        try:
            # Kết nối tới container chromadb thông qua tên service 'chromadb' trên Docker network
            _chroma_client = chromadb.HttpClient(
                host="chromadb", 
                port=8000,
                settings=Settings(allow_reset=True, anonymized_telemetry=False)
            )
            logger.info("✅ Connected to ChromaDB")
        except Exception as e:
            logger.error(f"❌ Failed to connect to ChromaDB: {e}")
    return _chroma_client

def get_news_collection():
    client = get_chroma_client()
    if client:
        try:
            # Lấy hoặc tạo collection để lưu tin tức
            return client.get_or_create_collection(name="market_news")
        except Exception as e:
            logger.error(f"❌ Failed to get collection: {e}")
    return None

async def push_to_ai_vector_embedder(symbol, headline, summary, content, url, ts_ms):
    """
    Chèn tin tức vào ChromaDB để chatbot có thể truy vấn (RAG).
    """
    collection = get_news_collection()
    if not collection:
        return
        
    doc_id = f"{symbol}_{ts_ms}"
    # Nội dung kết hợp để embedding tốt hơn
    text = f"SYMBOL: {symbol}\nHEADLINE: {headline}\nSUMMARY: {summary}\nCONTENT: {content}"
    
    try:
        # ChromaDB default embedding function sẽ tự động vector hóa text
        collection.upsert(
            documents=[text],
            metadatas=[{
                "symbol": symbol, 
                "url": url, 
                "timestamp": ts_ms, 
                "headline": headline
            }],
            ids=[doc_id]
        )
        print(f"🧠 [VectorDB] Đã index tin tức cho {symbol}: {headline[:50]}...")
    except Exception as e:
        print(f"❌ [VectorDB] Lỗi index: {e}")
