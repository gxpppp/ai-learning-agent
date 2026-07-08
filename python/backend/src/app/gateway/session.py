"""Session persistence — JSONL-based session store."""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field

from app.constants import VAULT_DOT_DIR

logger = logging.getLogger(__name__)


@dataclass
class SessionRecord:
    session_id: str
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    messages: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


def _session_dir(vault_path: str) -> str:
    return os.path.join(vault_path, VAULT_DOT_DIR, "sessions")


def _ensure_dir(vault_path: str) -> str:
    d = _session_dir(vault_path)
    os.makedirs(d, exist_ok=True)
    return d


def _session_path(vault_path: str, session_id: str) -> str:
    return os.path.join(_ensure_dir(vault_path), f"{session_id}.jsonl")


def create_session(vault_path: str, metadata: dict | None = None) -> SessionRecord:
    """Create a new session."""
    session_id = f"session_{int(time.time())}"
    record = SessionRecord(
        session_id=session_id,
        metadata=metadata or {},
    )
    _write_record(vault_path, record)
    return record


def load_session(vault_path: str, session_id: str) -> SessionRecord | None:
    """Load a session by ID."""
    path = _session_path(vault_path, session_id)
    if not os.path.exists(path):
        return None

    messages = []
    metadata = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                if entry.get("type") == "metadata":
                    metadata = entry.get("data", {})
                elif entry.get("type") == "message":
                    messages.append(entry.get("data", {}))
            except json.JSONDecodeError:
                continue

    return SessionRecord(
        session_id=session_id,
        created_at=metadata.get("created_at", os.path.getmtime(path)),
        updated_at=os.path.getmtime(path),
        messages=messages,
        metadata=metadata,
    )


def save_message(vault_path: str, session_id: str, msg: dict) -> None:
    """Append a message to a session file."""
    path = _session_path(vault_path, session_id)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"type": "message", "data": msg}, ensure_ascii=False) + "\n")


def list_sessions(vault_path: str, limit: int = 20) -> list[SessionRecord]:
    """List recent sessions."""
    d = _ensure_dir(vault_path)
    records = []
    for fname in os.listdir(d):
        if fname.endswith(".jsonl"):
            session_id = fname.replace(".jsonl", "")
            record = load_session(vault_path, session_id)
            if record:
                records.append(record)

    records.sort(key=lambda r: r.updated_at, reverse=True)
    return records[:limit]


def _write_record(vault_path: str, record: SessionRecord) -> None:
    """Write a new session record (creates the file)."""
    path = _session_path(vault_path, record.session_id)
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps({
            "type": "metadata",
            "data": {
                "created_at": record.created_at,
                **record.metadata,
            },
        }, ensure_ascii=False) + "\n")
