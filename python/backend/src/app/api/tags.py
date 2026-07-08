"""Tag suggestion and link recommendation endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.infra.embedding import EmbeddingClient
from app.infra.tag_engine import recommend_links as _recommend_links
from app.infra.tag_engine import suggest_tags as _suggest_tags
from app.infra.vector_store import VectorStore
from app.models.tag import (
    LinkRecommendRequest,
    LinkRecommendResponse,
    TagSuggestRequest,
    TagSuggestResponse,
)

router = APIRouter(prefix="/api", tags=["tags"])

embedding_client: EmbeddingClient | None = None
vector_store: VectorStore | None = None
vault_path: str = ""


def init_tags(emb: EmbeddingClient, store: VectorStore, vpath: str) -> None:
    global embedding_client, vector_store, vault_path
    embedding_client = emb
    vector_store = store
    vault_path = vpath


@router.post("/tags/suggest", response_model=TagSuggestResponse)
async def suggest_tags(body: TagSuggestRequest) -> TagSuggestResponse:
    if not embedding_client or not vector_store:
        raise HTTPException(status_code=503, detail="Service not initialized")
    result = _suggest_tags(
        body.note_path, vault_path, embedding_client, vector_store, body.max_tags
    )
    return TagSuggestResponse(**result)


@router.post("/links/recommend", response_model=LinkRecommendResponse)
async def recommend_links(body: LinkRecommendRequest) -> LinkRecommendResponse:
    if not embedding_client or not vector_store:
        raise HTTPException(status_code=503, detail="Service not initialized")
    result = _recommend_links(
        body.note_path, vault_path, embedding_client, vector_store, body.max_links
    )
    return LinkRecommendResponse(**result)
