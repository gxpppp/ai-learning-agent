"""OCR endpoints using local PaddleOCR (traditional, CPU)."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.config import OCR_ENABLED
from app.models.ocr import (
    OcrHealthResponse,
    OcrParseAndSaveRequest,
    OcrParseAndSaveResponse,
    OcrParseRequest,
    OcrParseResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ocr", tags=["ocr"])

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"}

_ocr_engine = None


def _get_ocr():
    """Lazy-load PaddleOCR engine."""
    global _ocr_engine
    if _ocr_engine is None:
        import os, glob, platform
        # PaddlePaddle needs CUDNN 9.9+; prefer pip-installed DLLs over system
        if platform.system() == "Windows":
            site_packages = os.path.dirname(os.path.dirname(__file__))
            for cudnn_bin in glob.glob(os.path.join(site_packages, "..", ".venv", "Lib", "site-packages", "nvidia", "cudnn", "bin")):
                os.add_dll_directory(os.path.abspath(cudnn_bin))
                break
        from paddleocr import PaddleOCR
        _ocr_engine = PaddleOCR(lang="ch", use_angle_cls=True)
        logger.info("PaddleOCR engine loaded")
    return _ocr_engine


async def _call_ocr(file_path: str, _task: str = "ocr") -> str:
    """Extract text from image using PaddleOCR."""
    ocr = _get_ocr()
    results = ocr.ocr(file_path)
    if not results:
        return ""

    lines: list[str] = []
    for page in results:
        if hasattr(page, "json"):
            data = page.json
            res = data.get("res", data)
            rec_texts = res.get("rec_texts", [])
            if isinstance(rec_texts, list):
                for text in rec_texts:
                    if isinstance(text, str) and text.strip():
                        lines.append(text.strip())
                    elif isinstance(text, list):
                        for t in text:
                            if isinstance(t, str) and t.strip():
                                lines.append(t.strip())
    return "\n".join(lines)


@router.get("/health", response_model=OcrHealthResponse)
async def ocr_health() -> OcrHealthResponse:
    if not OCR_ENABLED:
        raise HTTPException(status_code=503, detail="OCR service is disabled")
    try:
        _get_ocr()
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

    markdown = await _call_ocr(body.file_path, body.task)
    return OcrParseResponse(success=True, markdown=markdown)


@router.post("/parse-and-save", response_model=OcrParseAndSaveResponse)
async def parse_and_save(body: OcrParseAndSaveRequest) -> OcrParseAndSaveResponse:
    if not OCR_ENABLED:
        raise HTTPException(status_code=503, detail="OCR service is disabled")

    ext = Path(body.file_path).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=422, detail=f"Unsupported type: {ext}")

    markdown = await _call_ocr(body.file_path, body.task)

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

    return OcrParseAndSaveResponse(success=True, markdown=markdown, saved_path=f"{folder}/{filename}")
