"""OCR endpoints — local PaddleOCR-VL model or vLLM API."""

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

_local_model = None
_local_processor = None
_local_ready = False


def _get_local_model_path() -> str:
    """Get the local PaddleOCR-VL model path."""
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    return os.path.join(backend_dir, "models", "paddleocr-vl")


def _load_local_model() -> None:
    """Lazy-load the local PaddleOCR-VL model (pyTorch)."""
    global _local_model, _local_processor, _local_ready
    if _local_ready:
        return

    model_path = _get_local_model_path()
    if not os.path.isdir(model_path):
        logger.warning("Local PaddleOCR-VL not found at %s", model_path)
        return

    try:
        import torch
        from transformers import AutoModel, AutoProcessor

        _local_processor = AutoProcessor.from_pretrained(model_path, trust_remote_code=True)
        _local_model = AutoModel.from_pretrained(
            model_path,
            trust_remote_code=True,
            dtype=torch.float16,
            device_map="auto",
        )
        _local_ready = True
        logger.info("Local PaddleOCR-VL loaded (%s)", model_path)
    except Exception as e:
        logger.warning("Failed to load local PaddleOCR-VL: %s", e)


def _read_file_as_base64(file_path: str) -> tuple[str, str]:
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
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".bmp": "image/bmp", ".tiff": "image/tiff", ".tif": "image/tiff",
        ".webp": "image/webp", ".pdf": "application/pdf",
    }
    mime_type = mime_map.get(ext, "application/octet-stream")

    with open(file_path, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")
    return data, mime_type


async def _call_ocr_local(file_path: str, task: str) -> str:
    """OCR using local PaddleOCR-VL model."""
    if not _local_ready:
        _load_local_model()
    if not _local_model:
        raise HTTPException(status_code=503, detail="Local OCR model not available")

    from PIL import Image
    import torch

    img = Image.open(file_path).convert("RGB")
    prompt = TASK_PROMPTS.get(task, TASK_PROMPTS["ocr"])
    messages = [
        {"role": "user", "content": [
            {"type": "image", "image": img},
            {"type": "text", "text": prompt},
        ]},
    ]
    inputs = _local_processor.apply_chat_template(
        messages, add_generation_prompt=True, tokenize=True,
        return_dict=True, return_tensors="pt",
    ).to(_local_model.device)  # type: ignore[union-attr]

    with torch.no_grad():
        outputs = _local_model.generate(**inputs, max_new_tokens=2048, do_sample=False)

    result = _local_processor.decode(outputs[0], skip_special_tokens=True)  # type: ignore[union-attr]
    # Strip the prompt from the output
    if prompt in result:
        result = result.split(prompt, 1)[-1].strip()
    return result


async def _call_ocr(file_path: str, task: str) -> str:
    """Send file to PaddleOCR-VL (local model preferred, vLLM fallback)."""
    # Try local model first
    try:
        _load_local_model()
        if _local_ready:
            return await _call_ocr_local(file_path, task)
    except Exception as e:
        logger.warning("Local OCR failed, trying vLLM: %s", e)

    # Fallback to vLLM/Docker
    img_b64, mime_type = _read_file_as_base64(file_path)
    prompt_text = TASK_PROMPTS.get(task, TASK_PROMPTS["ocr"])
    try:
        response = await ocr_client.async_client.chat.completions.create(
            model=OCR_MODEL,
            messages=[
                {"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{img_b64}"}},
                    {"type": "text", "text": prompt_text},
                ]},
            ],
            temperature=0.0,
        )
        return response.choices[0].message.content or ""
    except Exception as exc:
        logger.exception("OCR request failed")
        raise HTTPException(status_code=502, detail=f"OCR service error: {exc}") from exc


@router.get("/health", response_model=OcrHealthResponse)
async def ocr_health() -> OcrHealthResponse:
    if not OCR_ENABLED:
        raise HTTPException(status_code=503, detail="OCR service is disabled")
    _load_local_model()
    if _local_ready:
        return OcrHealthResponse(status="ok", model="PaddleOCR-VL-0.9B (local)", server="local")
    try:
        await ocr_client.async_client.models.list()
        return OcrHealthResponse(status="ok", model=OCR_MODEL, server=OCR_SERVER_URL)
    except Exception:
        return OcrHealthResponse(status="ok", model="not-connected", server="none")


@router.post("/parse", response_model=OcrParseResponse)
async def parse_document(body: OcrParseRequest) -> OcrParseResponse:
    if not OCR_ENABLED:
        raise HTTPException(status_code=503, detail="OCR service is disabled")
    if body.task not in TASK_PROMPTS:
        raise HTTPException(status_code=422, detail=f"Invalid task: {body.task}")

    markdown = await _call_ocr(body.file_path, body.task)
    return OcrParseResponse(success=True, markdown=markdown)


@router.post("/parse-and-save", response_model=OcrParseAndSaveResponse)
async def parse_and_save(body: OcrParseAndSaveRequest) -> OcrParseAndSaveResponse:
    if not OCR_ENABLED:
        raise HTTPException(status_code=503, detail="OCR service is disabled")
    if body.task not in TASK_PROMPTS:
        raise HTTPException(status_code=422, detail=f"Invalid task: {body.task}")

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
