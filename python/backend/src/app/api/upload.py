"""File upload endpoint — auto-processes and vectorizes uploaded files.

Files are saved, OCRed if needed, and auto-vectorized.
LLM never sees raw file paths — it discovers content via search_notes/read_note tools.
"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile

from app.config import OBSIDIAN_VAULT_PATH
from app.infra.upload_pipeline import PROCESSABLE_EXTENSIONS, TEXT_EXTENSIONS, process_upload

router = APIRouter(prefix="/api/upload", tags=["upload"])

ALLOWED_EXTENSIONS = PROCESSABLE_EXTENSIONS | TEXT_EXTENSIONS
MAX_FILE_SIZE = 100 * 1024 * 1024


@router.post("/")
async def upload_file(file: UploadFile) -> dict:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    if not OBSIDIAN_VAULT_PATH:
        raise HTTPException(status_code=400, detail="Vault path not configured")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported type: {ext}. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # Save original file
    upload_dir = os.path.join(OBSIDIAN_VAULT_PATH, ".ai-tutor", "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    safe_name = Path(file.filename).name
    raw_path = os.path.join(upload_dir, f"{int(time.time())}_{safe_name}")

    with open(raw_path, "wb") as f:
        shutil.copyfileobj(file.file, f, length=1024 * 1024)

    # Process (OCR + vectorize)
    result = await process_upload(raw_path, OBSIDIAN_VAULT_PATH)

    return {
        "filename": file.filename,
        "size": os.path.getsize(raw_path),
        **result,
    }
