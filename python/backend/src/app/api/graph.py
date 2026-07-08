"""Knowledge graph endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.config import OBSIDIAN_VAULT_PATH
from app.infra.graph import generate_graph

router = APIRouter(prefix="/api/graph", tags=["graph"])


@router.get("/")
async def get_graph(
    folder: str | None = Query(None),
    max_nodes: int = Query(100, ge=10, le=500),
) -> dict:
    """Generate knowledge graph data from vault notes."""
    if not OBSIDIAN_VAULT_PATH:
        raise HTTPException(status_code=400, detail="Vault path not configured")
    return generate_graph(OBSIDIAN_VAULT_PATH, folder, max_nodes)
