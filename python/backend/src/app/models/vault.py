"""Pydantic models for vault indexing API."""

from __future__ import annotations

from pydantic import BaseModel


class VaultIndexRequest(BaseModel):
    vault_path: str
    force_reindex: bool = False


class VaultIndexResponse(BaseModel):
    status: str
    total_files: int = 0
    indexed_files: int = 0
    skipped_files: int = 0
    total_chunks: int = 0
    estimated_minutes: float = 0.0


class VaultStatusResponse(BaseModel):
    total_files: int
    indexed_files: int
    last_indexed: str | None = None
    status: str
