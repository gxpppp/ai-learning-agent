"""Document export endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.config import OBSIDIAN_VAULT_PATH
from app.infra.exporter import export_to_markdown

router = APIRouter(prefix="/api/export", tags=["export"])


@router.post("/")
async def export_vault(
    output_dir: str = Query(..., description="Absolute output directory"),
    folder: str | None = Query(None),
    tag: list[str] | None = Query(None),
) -> dict:
    """Export vault notes as VitePress-compatible docs."""
    if not OBSIDIAN_VAULT_PATH:
        raise HTTPException(status_code=400, detail="Vault path not configured")
    return export_to_markdown(OBSIDIAN_VAULT_PATH, output_dir, folder, tag)
