"""OCR engine — PaddleOCR-VL via Docker vLLM (OpenAI-compatible API).

PDFs are rendered page-by-page via PyMuPDF, then each page image
is sent to the VL model for OCR. All local — zero PaddlePaddle deps.
"""

from __future__ import annotations

import base64
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp", ".pdf"}


async def extract_text(file_path: str, dpi: int = 200) -> str:
    """Extract text from image or PDF via PaddleOCR-VL Docker service.

    - Images: base64 encode → VL model
    - PDFs: PyMuPDF renders each page → VL model per page
    """
    ext = Path(file_path).suffix.lower()

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    if ext == ".pdf":
        return await _extract_pdf(file_path, dpi)

    return await _ocr_image(file_path)


def _encode_image(file_path: str) -> tuple[str, str]:
    """Read image file and return (base64_string, mime_type)."""
    ext = os.path.splitext(file_path)[1].lower()
    mime_map = {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".bmp": "image/bmp", ".tiff": "image/tiff", ".tif": "image/tiff",
        ".webp": "image/webp",
    }
    mime = mime_map.get(ext, "application/octet-stream")
    with open(file_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return b64, mime


async def _ocr_image(file_path: str) -> str:
    """Send a single image to PaddleOCR-VL for OCR."""
    from app.config import OCR_ENABLED, OCR_MODEL, OCR_SERVER_URL
    if not OCR_ENABLED:
        return ""

    b64, mime = _encode_image(file_path)
    from app.llm.client import LLMClient
    client = LLMClient(OCR_SERVER_URL, "not-needed", OCR_MODEL)

    resp = await client.async_client.chat.completions.create(
        model=OCR_MODEL,
        messages=[{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
            {"type": "text", "text": "OCR: Extract all text. Output as Markdown."},
        ]}],
        temperature=0.0,
        max_tokens=2048,
    )
    return resp.choices[0].message.content or ""


async def _extract_pdf(file_path: str, dpi: int = 200) -> str:
    """Render PDF pages to images, OCR each page via VL, concatenate results."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.error("PyMuPDF not installed — cannot OCR PDFs")
        return ""

    doc = fitz.open(file_path)
    all_lines: list[str] = []

    for page_num in range(doc.page_count):
        page = doc[page_num]
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        img_path = f"{file_path}_page_{page_num}.png"

        try:
            pix.save(img_path)
            text = await _ocr_image(img_path)
            if text.strip():
                all_lines.append(f"## Page {page_num + 1}\n\n{text}")
        finally:
            if os.path.exists(img_path):
                os.unlink(img_path)

    doc.close()
    return "\n\n".join(all_lines)


def get_ocr_engine():
    """No local engine — always returns None. OCR goes through Docker VL."""
    return None
