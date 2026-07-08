"""Pydantic models for notes API."""

from __future__ import annotations

from pydantic import BaseModel


class NoteCreateRequest(BaseModel):
    vault_path: str
    folder: str
    filename: str
    content: str


class NoteReadRequest(BaseModel):
    vault_path: str
    path: str


class NoteUpdateRequest(BaseModel):
    vault_path: str
    path: str
    content: str


class NoteDeleteRequest(BaseModel):
    vault_path: str
    path: str


class NoteOperationResult(BaseModel):
    success: bool
    path: str | None = None
    content: str | None = None
    error: str | None = None
