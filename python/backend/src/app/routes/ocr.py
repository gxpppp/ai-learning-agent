"""OCR endpoints using PaddleOCR-VL via vLLM (OpenAI-compatible API)."""

from __future__ import annotations

import base64
import logging
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.config import OCR_ENABLED, OCR_MODEL, OCR_SERVER_URL
from app.models.ocr import (
    OcrHealthResponse,
    OcrParseAndSaveRequest,
    OcrParseAndSaveResponse,
    OcrParseRequest,
    OcrParseResponse,
)
from app.services.llm_client import LLMClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ocr", tags=["ocr"])

ocr_client = LLMClient(base_url=OCR_SERVER_URL, api_key="not-needed", model=OCR_MODEL)

TASK_PROMPTS = {
    "ocr": "OCR:",
    "table": "Table Recognition:",
    "formula": "Formula Recognition:",
    "chart": "Chart Recognition:",
}

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp", ".pdf"}


def _read_file_as_base64(file_path: str) -> tuple[str, str]:
    """Read a file and return (base64_data, mime_type)."""
    path = Path(file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported file type: {ext}. Supported: {supported}",
        )

    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".bmp": "image/bmp",
        ".tiff": "image/tiff",
        ".tif": "image/tiff",
        ".webp": "image/webp",
        ".pdf": "application/pdf",
    }
    mime_type = mime_map.get(ext, "application/octet-stream")

    with open(file_path, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")

    return data, mime_type


async def _call_ocr(file_path: str, task: str) -> str:
    """Send file to PaddleOCR-VL and return extracted text."""
    img_b64, mime_type = _read_file_as_base64(file_path)
    prompt_text = TASK_PROMPTS.get(task, TASK_PROMPTS["ocr"])

    try:
        response = await ocr_client.async_client.chat.completions.create(
            model=OCR_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{img_b64}"},
                        },
                        {"type": "text", "text": prompt_text},
                    ],
                }
            ],
            temperature=0.0,
        )
        return response.choices[0].message.content or ""
    except Exception as exc:
        logger.exception("OCR request failed")
        raise HTTPException(
            status_code=502,
            detail=f"OCR service error: {exc}",
        ) from exc


@router.get("/health", response_model=OcrHealthResponse)
async def ocr_health() -> OcrHealthResponse:
    if not OCR_ENABLED:
        raise HTTPException(status_code=503, detail="OCR service is disabled (OCR_ENABLED=false)")
    try:
        await ocr_client.async_client.models.list()
        return OcrHealthResponse(
            status="ok",
            model=OCR_MODEL,
            server=OCR_SERVER_URL,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"OCR service unavailable: {exc}",
        ) from exc


@router.post("/parse", response_model=OcrParseResponse)
async def parse_document(body: OcrParseRequest) -> OcrParseResponse:
    if not OCR_ENABLED:
        raise HTTPException(status_code=503, detail="OCR service is disabled (OCR_ENABLED=false)")
    if body.task not in TASK_PROMPTS:
        valid = list(TASK_PROMPTS.keys())
        raise HTTPException(
            status_code=422,
            detail=f"Invalid task: {body.task}. Valid: {valid}",
        )

    markdown = await _call_ocr(body.file_path, body.task)
    return OcrParseResponse(success=True, markdown=markdown)


@router.post("/parse-and-save", response_model=OcrParseAndSaveResponse)
async def parse_and_save(body: OcrParseAndSaveRequest) -> OcrParseAndSaveResponse:
    if not OCR_ENABLED:
        raise HTTPException(status_code=503, detail="OCR service is disabled (OCR_ENABLED=false)")
    if body.task not in TASK_PROMPTS:
        valid = list(TASK_PROMPTS.keys())
        raise HTTPException(
            status_code=422,
            detail=f"Invalid task: {body.task}. Valid: {valid}",
        )

    markdown = await _call_ocr(body.file_path, body.task)

    # Determine filename
    if body.filename:
        filename = body.filename if body.filename.endswith(".md") else f"{body.filename}.md"
    else:
        stem = Path(body.file_path).stem
        filename = f"{stem}.md"

    # Write to vault
    folder = body.target_folder or "OCR"
    full_dir = os.path.join(body.vault_path, folder)
    os.makedirs(full_dir, exist_ok=True)
    full_path = os.path.join(full_dir, filename)

    with open(full_path, "w", encoding="utf-8") as f:
        f.write(markdown)

    saved_path = f"{folder}/{filename}"
    return OcrParseAndSaveResponse(success=True, markdown=markdown, saved_path=saved_path)
