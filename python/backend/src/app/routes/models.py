"""Model listing endpoint — fetch available models from a provider's /v1/models."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.llm_manager import llm_manager

router = APIRouter(prefix="/api/models", tags=["models"])


class FetchModelsRequest(BaseModel):
    provider_id: str


class FetchModelsResponse(BaseModel):
    models: list[str]


@router.post("/fetch", response_model=FetchModelsResponse)
async def fetch_models(body: FetchModelsRequest) -> FetchModelsResponse:
    if not llm_manager:
        raise HTTPException(status_code=503, detail="LLM Manager not initialized")
    try:
        models = await llm_manager.fetch_models(body.provider_id)
        return FetchModelsResponse(models=models)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
