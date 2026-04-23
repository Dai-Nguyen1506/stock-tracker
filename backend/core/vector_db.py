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
