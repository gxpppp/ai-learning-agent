"""Notes CRUD API endpoints."""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException

from app.models.notes import (
    NoteCreateRequest,
    NoteDeleteRequest,
    NoteOperationResult,
    NoteReadRequest,
    NoteUpdateRequest,
)

router = APIRouter(prefix="/api/notes", tags=["notes"])


def _safe_path(vault_path: str, rel_path: str) -> str:
    """Build an absolute path and guard against directory traversal."""
    full = os.path.normpath(os.path.join(vault_path, rel_path))
    if not full.startswith(os.path.normpath(vault_path)):
        raise HTTPException(status_code=403, detail="Path traversal denied")
    return full


@router.post("/create", response_model=NoteOperationResult)
async def create_note(body: NoteCreateRequest):
    full_path = _safe_path(body.vault_path, os.path.join(body.folder, body.filename))
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    if os.path.exists(full_path):
        return NoteOperationResult(success=False, error="File already exists", path=body.path if hasattr(body, 'path') else None)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(body.content)
    rel = os.path.relpath(full_path, body.vault_path).replace("\\", "/")
    return NoteOperationResult(success=True, path=rel)


@router.post("/read", response_model=NoteOperationResult)
async def read_note(body: NoteReadRequest):
    full_path = _safe_path(body.vault_path, body.path)
    if not os.path.exists(full_path):
        return NoteOperationResult(success=False, error="File not found")
    with open(full_path, "r", encoding="utf-8") as f:
        content = f.read()
    return NoteOperationResult(success=True, path=body.path, content=content)


@router.post("/update", response_model=NoteOperationResult)
async def update_note(body: NoteUpdateRequest):
    full_path = _safe_path(body.vault_path, body.path)
    if not os.path.exists(full_path):
        return NoteOperationResult(success=False, error="File not found")
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(body.content)
    return NoteOperationResult(success=True, path=body.path)


@router.post("/delete", response_model=NoteOperationResult)
async def delete_note(body: NoteDeleteRequest):
    full_path = _safe_path(body.vault_path, body.path)
    if not os.path.exists(full_path):
        return NoteOperationResult(success=False, error="File not found")
    os.remove(full_path)
    return NoteOperationResult(success=True, path=body.path)
