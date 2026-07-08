"""Pydantic models for RAG API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RagQueryRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=20)


class RagChunk(BaseModel):
    note_path: str
    content: str
    score: float


class RagQueryResponse(BaseModel):
    answer: str
    sources: list[RagChunk]
