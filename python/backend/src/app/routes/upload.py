"""File upload endpoint — saves user-uploaded files to vault temp directory."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile

from app.config import OBSIDIAN_VAULT_PATH

router = APIRouter(prefix="/api/upload", tags=["upload"])

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp", ".pdf"}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB


@router.post("/")
async def upload_file(file: UploadFile) -> dict:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported file type: {ext}. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    upload_dir = os.path.join(OBSIDIAN_VAULT_PATH, ".ai-tutor", "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    safe_name = Path(file.filename).name
    dest = os.path.join(upload_dir, safe_name)

    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f, length=1024 * 1024)

    return {
        "filename": file.filename,
        "file_path": dest,
        "mime": file.content_type or "application/octet-stream",
        "size": os.path.getsize(dest),
    }
