"""Word cloud generation endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.wordcloud import WordCloudRequest, WordCloudResponse
from app.services.wordcloud_service import generate_wordcloud

router = APIRouter(prefix="/api/wordcloud", tags=["wordcloud"])

vault_path: str = ""


def init_wordcloud(vpath: str) -> None:
    global vault_path
    vault_path = vpath


@router.post("/generate", response_model=WordCloudResponse)
async def generate(body: WordCloudRequest) -> WordCloudResponse:
    if not vault_path:
        raise HTTPException(status_code=503, detail="Vault path not configured")
    result = generate_wordcloud(vault_path, body.folder, body.top_n)
    return WordCloudResponse(**result)
