"""PaddleOCR service — local GPU OCR engine."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"}

_ocr_engine = None


def get_ocr_engine():
    """Lazy-load PaddleOCR engine (singleton)."""
    global _ocr_engine
    if _ocr_engine is None:
        from paddleocr import PaddleOCR
        _ocr_engine = PaddleOCR(lang="ch", use_angle_cls=True)
        logger.info("PaddleOCR engine loaded")
    return _ocr_engine


async def extract_text(file_path: str) -> str:
    """Extract text from image using PaddleOCR. Returns plain text."""
    ocr = get_ocr_engine()
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
