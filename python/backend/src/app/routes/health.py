"""Health check endpoint for sidecar liveness probe."""

from fastapi import APIRouter

from app.config import LLM_MODEL, VERSION

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "version": VERSION,
        "model": LLM_MODEL,
    }
