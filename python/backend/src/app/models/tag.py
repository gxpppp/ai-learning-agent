"""Pydantic models for tag and link APIs."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TagSuggestRequest(BaseModel):
    note_path: str
    max_tags: int = Field(default=5, ge=1, le=20)


class TagSuggestResponse(BaseModel):
    tags: list[str]
    confidence: float


class LinkRecommendRequest(BaseModel):
    note_path: str
    max_links: int = Field(default=5, ge=1, le=20)


class LinkRecommendItem(BaseModel):
    target: str
    context: str
    score: float


class LinkRecommendResponse(BaseModel):
    links: list[LinkRecommendItem]
