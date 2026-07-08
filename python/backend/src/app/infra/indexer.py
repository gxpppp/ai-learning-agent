"""Vault indexer — scans vault, chunks notes, computes embeddings, writes to LanceDB."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from typing import Any

from app.config import CHUNK_OVERLAP, CHUNK_SIZE
from app.infra.embedding import EmbeddingClient
from app.infra.vector_store import VectorStore

INDEX_STATE = "index_state.json"


def _split_text(text: str, chunk_size: int = 512, overlap: int = 64) -> list[str]:
    """Simple recursive character text splitter."""
    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


def _file_hash(file_path: str) -> str:
    with open(file_path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def _load_index_state(vault_path: str) -> dict[str, Any]:
    state_path = os.path.join(vault_path, ".ai-tutor", INDEX_STATE)
    if os.path.exists(state_path):
        with open(state_path, encoding="utf-8") as f:
            return json.load(f)
    return {"files": {}, "last_full_index": None}


def _save_index_state(vault_path: str, state: dict[str, Any]) -> None:
    state_dir = os.path.join(vault_path, ".ai-tutor")
    os.makedirs(state_dir, exist_ok=True)
    state_path = os.path.join(state_dir, INDEX_STATE)
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def _find_markdown_files(vault_path: str) -> list[str]:
    """Recursively find all .md files, skipping hidden dirs."""
    files: list[str] = []
    skip_dirs = {".obsidian", ".ai-tutor", ".trash", ".git"}
    for root, dirs, filenames in os.walk(vault_path):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for fname in filenames:
            if fname.endswith(".md"):
                files.append(os.path.join(root, fname))
    return files


def _strip_frontmatter(text: str) -> str:
    """Remove YAML frontmatter delimited by ---."""
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            return text[end + 3 :].strip()
    return text


def index_note(
    file_path: str,
    vault_path: str,
    embedding: EmbeddingClient,
    store: VectorStore,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> int:
    """Index a single note. Returns number of chunks indexed."""
    with open(file_path, encoding="utf-8") as f:
        raw = f.read()
    text = _strip_frontmatter(raw)
    if not text.strip():
        return 0

    rel_path = os.path.relpath(file_path, vault_path).replace("\\", "/")
    store.delete_by_note(rel_path)

    chunks = _split_text(text, chunk_size, overlap)
    if not chunks:
        return 0

    vectors = embedding.encode(chunks)
    note_hash = _file_hash(file_path)

    records: list[dict] = []
    for i, (chunk, vec) in enumerate(zip(chunks, vectors)):
        chunk_id = f"{rel_path}#chunk{i}"
        records.append(
            {
                "id": chunk_id,
                "note_path": rel_path,
                "content": chunk,
                "vector": vec,
                "chunk_index": i,
                "total_chunks": len(chunks),
            }
        )

    store.add_chunks(records)

    # Update index state
    state = _load_index_state(vault_path)
    state["files"][rel_path] = {
        "hash": note_hash,
        "chunks": len(chunks),
        "indexed_at": datetime.now(UTC).isoformat(),
    }
    _save_index_state(vault_path, state)

    return len(chunks)


def index_vault(
    vault_path: str,
    embedding: EmbeddingClient,
    store: VectorStore,
    force_reindex: bool = False,
) -> dict[str, Any]:
    """Index all markdown files in the vault. Returns status dict."""
    files = _find_markdown_files(vault_path)
    state = _load_index_state(vault_path)

    total = len(files)
    indexed = 0
    skipped = 0

    for file_path in files:
        rel_path = os.path.relpath(file_path, vault_path).replace("\\", "/")

        if not force_reindex and rel_path in state["files"]:
            current_hash = _file_hash(file_path)
            if state["files"][rel_path].get("hash") == current_hash:
                skipped += 1
                continue

        index_note(file_path, vault_path, embedding, store)
        indexed += 1

    state["last_full_index"] = datetime.now(UTC).isoformat()
    _save_index_state(vault_path, state)

    return {
        "total_files": total,
        "indexed_files": indexed,
        "skipped_files": skipped,
        "total_chunks": store.count(),
        "status": "idle",
    }


def remove_note(file_path: str, vault_path: str, store: VectorStore) -> None:
    """Remove a deleted note from the index."""
    rel_path = os.path.relpath(file_path, vault_path).replace("\\", "/")
    store.delete_by_note(rel_path)
    state = _load_index_state(vault_path)
    state["files"].pop(rel_path, None)
    _save_index_state(vault_path, state)
