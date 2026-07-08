"""OCR endpoints — delegate to infra/ocr engine."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.config import OCR_ENABLED
from app.infra.ocr import SUPPORTED_EXTENSIONS, extract_text, get_ocr_engine
from app.models.ocr import (
    OcrHealthResponse,
    OcrParseAndSaveRequest,
    OcrParseAndSaveResponse,
    OcrParseRequest,
    OcrParseResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ocr", tags=["ocr"])


@router.get("/health", response_model=OcrHealthResponse)
async def ocr_health() -> OcrHealthResponse:
    if not OCR_ENABLED:
        raise HTTPException(status_code=503, detail="OCR service is disabled")
    try:
        get_ocr_engine()
        return OcrHealthResponse(status="ok", model="PaddleOCR (local)", server="local")
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@router.post("/parse", response_model=OcrParseResponse)
async def parse_document(body: OcrParseRequest) -> OcrParseResponse:
    if not OCR_ENABLED:
        raise HTTPException(status_code=503, detail="OCR service is disabled")

    ext = Path(body.file_path).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=422, detail=f"Unsupported type: {ext}")

    markdown = await extract_text(body.file_path)
    return OcrParseResponse(success=True, markdown=markdown)


@router.post("/parse-and-save", response_model=OcrParseAndSaveResponse)
async def parse_and_save(body: OcrParseAndSaveRequest) -> OcrParseAndSaveResponse:
    if not OCR_ENABLED:
        raise HTTPException(status_code=503, detail="OCR service is disabled")

    ext = Path(body.file_path).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=422, detail=f"Unsupported type: {ext}")

    markdown = await extract_text(body.file_path)

    if body.filename:
        filename = body.filename if body.filename.endswith(".md") else f"{body.filename}.md"
    else:
        filename = f"{Path(body.file_path).stem}.md"

    folder = body.target_folder or "OCR"
    full_dir = os.path.normpath(os.path.join(body.vault_path, folder))
    norm_vault = os.path.normpath(body.vault_path)
    if not full_dir.startswith(norm_vault):
        raise HTTPException(status_code=403, detail="Path traversal denied")
    os.makedirs(full_dir, exist_ok=True)

    safe_name = os.path.basename(filename)
    full_path = os.path.normpath(os.path.join(full_dir, safe_name))
    if not full_path.startswith(norm_vault):
        raise HTTPException(status_code=403, detail="Path traversal denied")

    with open(full_path, "w", encoding="utf-8") as f:
        f.write(markdown)

    return OcrParseAndSaveResponse(
        success=True, markdown=markdown, saved_path=f"{folder}/{filename}"
    )
