"""Pydantic models for OCR API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

OCR_TASK = Literal["ocr", "table", "formula", "chart"]


class OcrParseRequest(BaseModel):
    file_path: str
    task: OCR_TASK = Field(default="ocr")


class OcrParseResponse(BaseModel):
    success: bool
    markdown: str | None = None
    error: str | None = None


class OcrParseAndSaveRequest(BaseModel):
    file_path: str
    vault_path: str
    target_folder: str = Field(default="OCR")
    filename: str | None = None
    task: OCR_TASK = Field(default="ocr")


class OcrParseAndSaveResponse(BaseModel):
    success: bool
    markdown: str | None = None
    saved_path: str | None = None
    error: str | None = None


class OcrHealthResponse(BaseModel):
    status: str
    model: str
    server: str
