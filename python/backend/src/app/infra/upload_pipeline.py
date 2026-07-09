"""Upload processing pipeline — auto-process uploaded files and vectorize.

Flow:
  upload → save raw → process (OCR if needed) → save .md to vault → vectorize → return status
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PROCESSABLE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp", ".pdf"}
TEXT_EXTENSIONS = {".md", ".txt", ".markdown"}


async def process_upload(
    raw_path: str,
    vault_path: str,
    target_folder: str = "Inbox",
) -> dict[str, Any]:
    """Process an uploaded file: OCR if needed, save to vault, vectorize.

    Returns {"status":"done", "name":"xxx.md", "size":N, "chunks":N, "type":"pdf|image|text"}
    """
    ext = Path(raw_path).suffix.lower()
    stem = Path(raw_path).stem
    target_dir = os.path.join(vault_path, target_folder)
    md_path = os.path.join(target_dir, f"{stem}.md")

    # Step 1: Process raw file into markdown
    if ext == ".md":
        # Markdown: just copy
        os.makedirs(target_dir, exist_ok=True)
        shutil.copy2(raw_path, md_path)
        md_content = _read_file(md_path)
        file_type = "text"
    elif ext == ".pdf":
        # PDF: PyMuPDF + PaddleOCR
        try:
            from app.infra.ocr import extract_text
            md_content = await extract_text(raw_path)
        except Exception as e:
            logger.exception("PDF OCR failed")
            return {"status": "error", "reason": f"OCR failed: {e}", "name": f"{stem}.pdf"}
        os.makedirs(target_dir, exist_ok=True)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        file_type = "pdf"
    elif ext in PROCESSABLE_EXTENSIONS:
        # Image: PaddleOCR
        try:
            from app.infra.ocr import extract_text
            md_content = await extract_text(raw_path)
        except Exception as e:
            logger.exception("Image OCR failed")
            return {"status": "error", "reason": f"OCR failed: {e}", "name": f"{stem}{ext}"}
    else:
        return {"status": "skipped", "reason": f"Unsupported format: {ext}"}

    # Step 2: Vectorize the resulting .md
    chunks = 0
    try:
        from app.config import EMBEDDING_SERVER_URL, RAG_ENABLED
        if RAG_ENABLED:
            from app.infra.embedding import EmbeddingClient
            from app.infra.indexer import index_note
            emb = EmbeddingClient(EMBEDDING_SERVER_URL)
            chunk_count = index_note(md_path, vault_path, emb, None)  # type: ignore[arg-type]
            chunks = chunk_count if isinstance(chunk_count, int) else 0
    except Exception:
        logger.exception("vectorize failed")

    rel_path = os.path.relpath(md_path, vault_path).replace("\\", "/")

    return {
        "status": "done",
        "name": f"{stem}.md",
        "path": rel_path,
        "size": os.path.getsize(md_path),
        "chunks": chunks,
        "type": file_type,
    }


def _read_file(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()
