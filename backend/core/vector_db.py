import os
import time
import chromadb
from chromadb.config import Settings
from core.config import settings
from core.logger import logger

try:
    import posthog
    posthog.capture = lambda *args, **kwargs: None
except (ImportError, AttributeError):
    pass

_chroma_client = None

def get_chroma_client():
    """
    Initializes and returns the ChromaDB HTTP client with retry logic.
    """
    global _chroma_client
    if _chroma_client is None:
        for i in range(3):
            try:
                _chroma_client = chromadb.HttpClient(
                    host=settings.CHROMA_HOST, 
                    port=settings.CHROMA_PORT,
                    settings=Settings(allow_reset=True, anonymized_telemetry=False)
                )
                logger.info("[VectorDB] Connected to ChromaDB")
                break
            except Exception as e:
                if i == 2:
                    logger.error(f"[VectorDB] Connection failed after 3 retries: {e}")
                else:
                    time.sleep(2)
    return _chroma_client

def get_news_collection():
    """
    Retrieves or creates the 'market_news' collection in ChromaDB.
    """
    client = get_chroma_client()
    if client:
        try:
            return client.get_or_create_collection(name="market_news")
        except Exception as e:
            logger.error(f"[VectorDB] Failed to get collection: {e}")
    return None

async def push_to_ai_vector_embedder(symbol, headline, summary, content, url, ts_ms):
    """
    Inserts or updates news items in ChromaDB for RAG-based retrieval.
    """
    collection = get_news_collection()
    if not collection:
        return
        
    doc_id = f"{symbol}_{ts_ms}"
    text = f"SYMBOL: {symbol}\nHEADLINE: {headline}\nSUMMARY: {summary}\nCONTENT: {content}"
    
    try:
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
        logger.debug(f"[VectorDB] Indexed news for {symbol}: {headline[:50]}...")
    except Exception as e:
        logger.error(f"[VectorDB] Indexing failed for {symbol}: {e}")
