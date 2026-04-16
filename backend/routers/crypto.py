from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def list_crypto():
    """Placeholder — sẽ bổ sung ở Giai đoạn 2"""
    return {"message": "Crypto API ready", "pairs": []}