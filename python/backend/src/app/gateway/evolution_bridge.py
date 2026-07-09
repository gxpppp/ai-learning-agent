"""Evolution bridge — connects the evolution engine to gateway agent prompts.

When the evolution engine discovers a better prompt, this bridge syncs it
into the gateway's agent definitions and the agent.py system prompt.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def get_active_prompt(vault_path: str) -> str | None:
    """Get the currently deployed best prompt from evolution output."""
    evolution_dir = os.path.join(vault_path, ".ai-tutor", "evolution")
    active_path = os.path.join(evolution_dir, "VARIANTS", "active.md")
    if not os.path.exists(active_path):
        return None
    try:
        with open(active_path, encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        logger.exception("Failed to read active evolution prompt")
        return None


def inject_evolved_prompt(base_prompt: str, vault_path: str) -> str:
    """If an evolved prompt exists, prepend it as optimization notes."""
    evolved = get_active_prompt(vault_path)
    if evolved and evolved.strip():
        return (
            f"{base_prompt}\n\n"
            f"## Optimized Instructions (from evolution)\n"
            f"{evolved}"
        )
    return base_prompt


def sync_to_gateway(vault_path: str) -> dict:
    """Sync the evolved prompt into gateway agent definitions.

    Returns status dict with what was updated.
    """
    evolved = get_active_prompt(vault_path)
    if not evolved:
        return {"status": "no_evolution_data", "message": "No evolved prompt found"}

    # Update agent prompts
    from app.gateway.agents import AGENT_DEFINITIONS, ORCHESTRATOR_PROMPT

    orchestrator = AGENT_DEFINITIONS.get("orchestrator", {})
    orchestrator["system_prompt"] = inject_evolved_prompt(ORCHESTRATOR_PROMPT, vault_path)

    return {
        "status": "synced",
        "message": f"Evolved prompt injected ({len(evolved)} chars)",
        "agents_updated": ["orchestrator"],
    }


def get_best_prompt(vault_path: str) -> str:
    """Get the best available prompt: evolved if exists, otherwise default."""
    evolved = get_active_prompt(vault_path)
    if evolved:
        return evolved

    from app.llm.prompts import AGENT_SYSTEM_PROMPT

    return AGENT_SYSTEM_PROMPT.format(
        vault_path=vault_path,
        permission_mode="full",
    )
