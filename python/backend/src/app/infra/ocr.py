"""Unified OCR engine — PaddleOCR (GPU) for images + PyMuPDF→PaddleOCR for PDFs.

Single entry point: extract_text(file_path) handles both images and PDFs.
All processing is local — zero remote API dependencies.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp", ".pdf"}

_ocr_engine = None


def get_ocr_engine():
    """Lazy-load PaddleOCR engine (singleton)."""
    global _ocr_engine
    if _ocr_engine is None:
        from paddleocr import PaddleOCR
        _ocr_engine = PaddleOCR(lang="ch", use_angle_cls=True)
        logger.info("PaddleOCR engine loaded")
    return _ocr_engine


async def extract_text(file_path: str, dpi: int = 200) -> str:
    """Extract text from image or PDF. Returns plain text.

    - Images: PaddleOCR directly
    - PDFs: PyMuPDF renders each page to image → PaddleOCR
    """
    ext = Path(file_path).suffix.lower()

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    if ext == ".pdf":
        return _extract_pdf(file_path, dpi)

    return _extract_image(file_path)


def _extract_image(file_path: str) -> str:
    """Run PaddleOCR on a single image file."""
    ocr = get_ocr_engine()
    results = ocr.ocr(file_path)
    return _parse_results(results)


def _extract_pdf(file_path: str, dpi: int = 200) -> str:
    """Render PDF pages to images, OCR each page, concatenate results."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.error("PyMuPDF not installed — cannot OCR PDFs")
        return ""

    doc = fitz.open(file_path)
    all_lines: list[str] = []
    ocr = get_ocr_engine()

    for page_num in range(doc.page_count):
        page = doc[page_num]
        # Render page to pixmap (RGB)
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        img_path = f"{file_path}_page_{page_num}.png"

        try:
            pix.save(img_path)
            result = ocr.ocr(img_path)
            text = _parse_results(result)
            if text.strip():
                all_lines.append(f"## Page {page_num + 1}\n\n{text}")
        finally:
            if os.path.exists(img_path):
                os.unlink(img_path)

    doc.close()
    return "\n\n".join(all_lines)


def _parse_results(results) -> str:
    """Parse PaddleOCR results into text lines."""
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
