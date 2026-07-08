"""Pydantic models for word cloud API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class WordCloudRequest(BaseModel):
    folder: str | None = None
    top_n: int = Field(default=50, ge=10, le=200)


class WordCloudWord(BaseModel):
    word: str
    weight: float
    tfidf: float
    link_count: int


class WordCloudResponse(BaseModel):
    words: list[WordCloudWord]
    total_notes: int
    generated_at: str | None = None
