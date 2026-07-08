"""Obsidian vault file operations — safe read/write with path traversal protection."""

from __future__ import annotations

import os


def safe_path(vault_path: str, rel_path: str) -> str:
    """Resolve a relative vault path safely. Raises ValueError on path traversal."""
    full = os.path.normpath(os.path.join(vault_path, rel_path))
    if not full.startswith(os.path.normpath(vault_path)):
        raise ValueError("Path traversal denied")
    return full


def read_note(vault_path: str, note_path: str) -> str:
    """Read a note's full content."""
    full = safe_path(vault_path, note_path)
    if not os.path.exists(full):
        raise FileNotFoundError(f"Note not found: {note_path}")
    with open(full, encoding="utf-8") as f:
        return f.read()


def write_note(vault_path: str, note_path: str, content: str) -> str:
    """Write content to a note, creating parent dirs if needed."""
    full = safe_path(vault_path, note_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)
    return os.path.relpath(full, vault_path).replace("\\", "/")


def delete_note(vault_path: str, note_path: str) -> str:
    """Delete a note, moving it to .trash/."""
    full = safe_path(vault_path, note_path)
    if not os.path.exists(full):
        raise FileNotFoundError(f"Note not found: {note_path}")
    trash_dir = os.path.join(vault_path, ".trash")
    os.makedirs(trash_dir, exist_ok=True)
    dest = os.path.join(trash_dir, os.path.basename(note_path))
    os.rename(full, dest)
    return f".trash/{os.path.basename(note_path)}"


def list_folder(vault_path: str, path: str = "") -> list[dict]:
    """List contents of a vault folder."""
    full = safe_path(vault_path, path)
    if not os.path.isdir(full):
        raise FileNotFoundError(f"Folder not found: {path}")
    items = []
    with os.scandir(full) as it:
        for entry in sorted(it, key=lambda e: (not e.is_dir(), e.name.lower())):
            items.append({
                "name": entry.name,
                "type": "folder" if entry.is_dir() else "file",
                "size": entry.stat().st_size if entry.is_file() else 0,
            })
    return items


def create_folder(vault_path: str, path: str) -> str:
    """Create a folder in the vault."""
    full = safe_path(vault_path, path)
    os.makedirs(full, exist_ok=True)
    return path


def move_note(vault_path: str, source: str, destination: str) -> str:
    """Move or rename a note."""
    src = safe_path(vault_path, source)
    dst = safe_path(vault_path, destination)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    os.rename(src, dst)
    return destination
