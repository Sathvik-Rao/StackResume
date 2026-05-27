"""Meta endpoints — health probe."""
from datetime import datetime, timezone

from fastapi import APIRouter


router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/health")
async def health():
    return {"status": "ok", "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000)}
