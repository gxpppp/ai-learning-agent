"""Evolution integration endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.config import OBSIDIAN_VAULT_PATH
from app.gateway.evolution_bridge import get_active_prompt, sync_to_gateway

router = APIRouter(prefix="/api/evolution", tags=["evolution"])


@router.post("/sync")
async def sync_evolution() -> dict:
    """Sync evolution engine's best prompt into gateway agents."""
    if not OBSIDIAN_VAULT_PATH:
        raise HTTPException(status_code=400, detail="Vault path not configured")
    return sync_to_gateway(OBSIDIAN_VAULT_PATH)


@router.get("/active-prompt")
async def active_prompt() -> dict:
    """Get the currently active evolved prompt."""
    if not OBSIDIAN_VAULT_PATH:
        raise HTTPException(status_code=400, detail="Vault path not configured")
    prompt = get_active_prompt(OBSIDIAN_VAULT_PATH)
    return {"active_prompt": prompt or "No evolved prompt — using default"}
