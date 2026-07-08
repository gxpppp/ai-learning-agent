"""Persistent memory — stores user profile, preferences, and learning context."""

from __future__ import annotations

import json
import logging
import os
import time

from app.constants import VAULT_DOT_DIR

logger = logging.getLogger(__name__)

_MEMORY_CACHE: dict[str, dict] = {}


def _memory_dir(vault_path: str) -> str:
    return os.path.join(vault_path, VAULT_DOT_DIR, "memory")


def _ensure_dir(vault_path: str) -> str:
    d = _memory_dir(vault_path)
    os.makedirs(d, exist_ok=True)
    return d


def load_memory(vault_path: str, key: str, default: dict | None = None) -> dict:
    """Load a memory entry from disk."""
    if key in _MEMORY_CACHE:
        return _MEMORY_CACHE[key]

    filepath = os.path.join(_ensure_dir(vault_path), f"{key}.json")
    if not os.path.exists(filepath):
        return default or {}

    try:
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)
        _MEMORY_CACHE[key] = data
        return data
    except Exception:
        logger.exception(f"Failed to load memory: {key}")
        return default or {}


def save_memory(vault_path: str, key: str, data: dict) -> None:
    """Save a memory entry to disk."""
    _MEMORY_CACHE[key] = data
    filepath = os.path.join(_ensure_dir(vault_path), f"{key}.json")
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        logger.exception(f"Failed to save memory: {key}")


def load_user_profile(vault_path: str) -> dict:
    """Load the user profile."""
    return load_memory(vault_path, "user_profile", {
        "name": "",
        "preferences": {},
        "recent_topics": [],
    })


def save_user_profile(vault_path: str, profile: dict) -> None:
    """Save the user profile."""
    save_memory(vault_path, "user_profile", profile)


def add_recent_topic(vault_path: str, topic: str) -> None:
    """Track a recently discussed topic."""
    profile = load_user_profile(vault_path)
    topics = profile.get("recent_topics", [])
    if topic in topics:
        topics.remove(topic)
    topics.insert(0, topic)
    profile["recent_topics"] = topics[:20]
    save_user_profile(vault_path, profile)


def load_conversation_context(vault_path: str) -> dict:
    """Load cross-session conversation context."""
    return load_memory(vault_path, "conversation_context", {
        "ongoing_tasks": [],
        "pending_actions": [],
        "last_session": None,
    })


def save_conversation_context(vault_path: str, context: dict) -> None:
    """Save cross-session conversation context."""
    context["last_session"] = time.time()
    save_memory(vault_path, "conversation_context", context)
