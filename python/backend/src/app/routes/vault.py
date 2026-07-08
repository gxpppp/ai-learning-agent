"""Vault indexing endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.vault import VaultIndexRequest, VaultIndexResponse, VaultStatusResponse
from app.services.embedding import EmbeddingClient
from app.services.indexer import _load_index_state, index_vault
from app.services.vector_store import VectorStore

router = APIRouter(prefix="/api/vault", tags=["vault"])

embedding_client: EmbeddingClient | None = None
vector_store: VectorStore | None = None
vault_path: str = ""
_indexing_status: str = "idle"


def init_vault(emb: EmbeddingClient, store: VectorStore, vpath: str) -> None:
    global embedding_client, vector_store, vault_path
    embedding_client = emb
    vector_store = store
    vault_path = vpath


@router.post("/index", response_model=VaultIndexResponse)
async def trigger_index(body: VaultIndexRequest) -> VaultIndexResponse:
    global _indexing_status
    if not embedding_client or not vector_store:
        raise HTTPException(status_code=503, detail="Service not initialized")

    vpath = body.vault_path or vault_path
    if not vpath:
        raise HTTPException(status_code=400, detail="Vault path is required")

    _indexing_status = "indexing"
    try:
        result = index_vault(vpath, embedding_client, vector_store, body.force_reindex)
        _indexing_status = "idle"
        total = result.get("total_files", 0) or 1
        minutes = round((result.get("indexed_files", 0) / total) * 0.5, 1)
        return VaultIndexResponse(
            status="idle",
            total_files=result["total_files"],
            indexed_files=result["indexed_files"],
            skipped_files=result["skipped_files"],
            total_chunks=result["total_chunks"],
            estimated_minutes=minutes,
        )
    except Exception as exc:
        _indexing_status = "error"
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/status", response_model=VaultStatusResponse)
async def get_status() -> VaultStatusResponse:
    if not vault_path:
        return VaultStatusResponse(total_files=0, indexed_files=0, status="no_vault")

    state = _load_index_state(vault_path)
    return VaultStatusResponse(
        total_files=len(state.get("files", {})),
        indexed_files=len(state.get("files", {})),
        last_indexed=state.get("last_full_index"),
        status=_indexing_status,
    )
