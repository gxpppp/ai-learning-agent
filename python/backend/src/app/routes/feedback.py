"""Feedback endpoint — records user thumbs up/down to evolution/feedback.jsonl."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import OBSIDIAN_VAULT_PATH

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


class FeedbackRequest(BaseModel):
    rating: str  # thumbs_up | thumbs_down
    reason: str = ""
    session_id: str = ""


@router.post("")
async def submit_feedback(body: FeedbackRequest) -> dict:
    evolution_dir = os.path.join(OBSIDIAN_VAULT_PATH, ".ai-tutor", "evolution")
    os.makedirs(evolution_dir, exist_ok=True)

    entry = {
        "id": f"fb_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}",
        "session": body.session_id,
        "rating": body.rating,
        "reason": body.reason,
        "timestamp": datetime.now(UTC).isoformat(),
    }

    file_path = os.path.join(evolution_dir, "feedback.jsonl")
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return {"status": "ok"}
