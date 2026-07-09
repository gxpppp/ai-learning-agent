"""Tool registry — defines tools in OpenAI function-calling format and executes them.

Tools are split into readonly and full-access groups.
The active permission mode determines which tools are registered.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger("tool")

READONLY_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_notes",
            "description": "Search the user's vault for notes matching a query using semantic search.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "top_k": {"type": "integer", "description": "Number of results", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_note",
            "description": "Read the full content of a note in the vault.",
            "parameters": {
                "type": "object",
                "properties": {
                    "note_path": {"type": "string", "description": "Path relative to vault root, e.g. 'Projects/ideas.md'"},
                },
                "required": ["note_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_folder",
            "description": "List the contents of a folder in the vault.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path relative to vault root", "default": ""},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "suggest_tags",
            "description": "Suggest frontmatter tags for a note based on its content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "note_path": {"type": "string", "description": "Path to the note"},
                    "max_tags": {"type": "integer", "default": 5},
                },
                "required": ["note_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recommend_links",
            "description": "Recommend bidirectional [[links]] between notes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "note_path": {"type": "string", "description": "Path to the note"},
                    "max_links": {"type": "integer", "default": 5},
                },
                "required": ["note_path"],
            },
        },
    },
]

FULL_TOOLS = READONLY_TOOLS + [
    {
        "type": "function",
        "function": {
            "name": "create_note",
            "description": "Create or overwrite a Markdown note in the vault.",
            "parameters": {
                "type": "object",
                "properties": {
                    "folder": {"type": "string", "description": "Target folder relative to vault root"},
                    "filename": {"type": "string", "description": "Filename with .md extension"},
                    "content": {"type": "string", "description": "Markdown content of the note"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "Frontmatter tags"},
                },
                "required": ["folder", "filename", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_note",
            "description": "Update the content of an existing note.",
            "parameters": {
                "type": "object",
                "properties": {
                    "note_path": {"type": "string", "description": "Path to the note"},
                    "content": {"type": "string", "description": "New Markdown content"},
                },
                "required": ["note_path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_note",
            "description": "Delete a note (moved to .trash folder).",
            "parameters": {
                "type": "object",
                "properties": {
                    "note_path": {"type": "string", "description": "Path to the note to delete"},
                },
                "required": ["note_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_folder",
            "description": "Create a folder in the vault.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path relative to vault root"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "move_note",
            "description": "Move or rename a note to a different location.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {"type": "string", "description": "Current path"},
                    "destination": {"type": "string", "description": "New path"},
                },
                "required": ["source", "destination"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ocr_document",
            "description": "Extract text from an image or PDF into Markdown. Saves result to vault.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Absolute path to the file"},
                    "output_folder": {"type": "string", "description": "Folder to save the result", "default": "OCR"},
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "classify_note",
            "description": "Classify a note by its content type (e.g. textbook, research paper, personal note).",
            "parameters": {
                "type": "object",
                "properties": {
                    "note_path": {"type": "string", "description": "Path to the note"},
                },
                "required": ["note_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_summary",
            "description": "Generate a TL;DR summary of a note and append it to the note.",
            "parameters": {
                "type": "object",
                "properties": {
                    "note_path": {"type": "string", "description": "Path to the note"},
                },
                "required": ["note_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_vault_status",
            "description": "Check the vault indexing and word cloud status.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def get_tools(permission_mode: str) -> list[dict]:
    if permission_mode == "full":
        return FULL_TOOLS
    return READONLY_TOOLS


async def execute_tool(
    name: str,
    args: dict[str, Any],
    vault_path: str,
    trace_id: str = "",
) -> str:
    """Execute a tool call and return the result as a string."""
    import time

    t0 = time.time()
    try:
        if name == "search_notes":
            return await _search_notes(args, vault_path)
        if name == "read_note":
            return _read_note(args, vault_path)
        if name == "list_folder":
            return _list_folder(args, vault_path)
        if name == "suggest_tags":
            return _suggest_tags(args, vault_path)
        if name == "recommend_links":
            return _recommend_links(args, vault_path)
        if name == "create_note":
            return _create_note(args, vault_path)
        if name == "update_note":
            return _update_note(args, vault_path)
        if name == "delete_note":
            return _delete_note(args, vault_path)
        if name == "create_folder":
            return _create_folder(args, vault_path)
        if name == "move_note":
            return _move_note(args, vault_path)
        if name == "ocr_document":
            return await _ocr_document(args, vault_path)
        if name == "classify_note":
            return _classify_note(args, vault_path)
        if name == "generate_summary":
            return await _generate_summary(args, vault_path)
        if name == "get_vault_status":
            return _get_vault_status(vault_path)
        return json.dumps({"error": f"Unknown tool: {name}"})
    except Exception as exc:
        import traceback
        logger.warning("tool error", extra={
            "trace_id": trace_id, "tool": name,
            "ms": int((time.time() - t0) * 1000),
            "error": str(exc),
        })
        logger.debug("traceback", extra={"trace_id": trace_id, "tb": traceback.format_exc()[-500:]})
        return json.dumps({"error": str(exc)})
    finally:
        ms = int((time.time() - t0) * 1000)
        logger.info("tool done", extra={
            "trace_id": trace_id, "tool": name,
            "ms": ms, "vault": vault_path[:40],
        })


# ─── Helpers ─────────────────────────────────────────────

def _safe_path(vault_path: str, rel_path: str) -> str:
    full = os.path.normpath(os.path.join(vault_path, rel_path))
    if not full.startswith(os.path.normpath(vault_path)):
        raise ValueError("Path traversal denied")
    return full


def _arg(args: dict, *keys: str, default: Any = "") -> Any:
    """Get first matching key from args (LLM may use different param names)."""
    for k in keys:
        if k in args and args[k]:
            return args[k]
    return default


def _is_binary(file_path: str) -> bool:
    """Quick check if file is binary (PDF/image/archive)."""
    try:
        with open(file_path, "rb") as f:
            head = f.read(2048)
        return b"\x00" in head
    except OSError:
        return False


async def _search_notes(args: dict, vault_path: str) -> str:
    from app.config import EMBEDDING_MODEL
    from app.infra.embedding import EmbeddingClient
    from app.infra.vector_store import VectorStore

    store = VectorStore(vault_path)
    if store.count() == 0:
        return json.dumps({"results": [], "message": "Vault not indexed yet. Use /api/vault/index first."})

    emb = EmbeddingClient(EMBEDDING_MODEL)
    query_vec = emb.encode_query(args["query"])
    results = store.search(query_vec, top_k=args.get("top_k", 5))
    return json.dumps({
        "results": [{"path": r["note_path"], "score": round(r["score"], 4), "excerpt": r["content"][:300]} for r in results],
    })


def _read_note(args: dict, vault_path: str) -> str:
    note_path = _arg(args, "note_path", "file_path", "path")
    if not note_path:
        return json.dumps({"error": "Missing note_path"})
    full = _safe_path(vault_path, note_path)
    if not os.path.exists(full):
        return json.dumps({"error": f"File not found: {note_path}"})
    if _is_binary(full):
        return json.dumps({"error": "Binary file (PDF/image). Use ocr_document tool instead.", "path": note_path})
    with open(full, encoding="utf-8") as f:
        content = f.read()
    return json.dumps({"path": note_path, "content": content})


def _list_folder(args: dict, vault_path: str) -> str:
    p = _arg(args, "path", "folder", "folder_path", "dir_path")
    full = _safe_path(vault_path, p)
    if not os.path.isdir(full):
        return json.dumps({"error": f"Folder not found: {p}"})
    items = []
    with os.scandir(full) as it:
        for entry in sorted(it, key=lambda e: (not e.is_dir(), e.name.lower())):
            items.append({
                "name": entry.name,
                "type": "folder" if entry.is_dir() else "file",
                "size": entry.stat().st_size if entry.is_file() else 0,
            })
    return json.dumps({"path": p, "items": items, "count": len(items)})


def _suggest_tags(args: dict, vault_path: str) -> str:
    from app.config import EMBEDDING_MODEL
    from app.infra.embedding import EmbeddingClient
    from app.infra.tag_engine import suggest_tags as _st
    from app.infra.vector_store import VectorStore

    store = VectorStore(vault_path)
    emb = EmbeddingClient(EMBEDDING_MODEL)
    result = _st(args["note_path"], vault_path, emb, store, args.get("max_tags", 5))
    return json.dumps(result)


def _recommend_links(args: dict, vault_path: str) -> str:
    from app.config import EMBEDDING_MODEL
    from app.infra.embedding import EmbeddingClient
    from app.infra.tag_engine import recommend_links as _rl
    from app.infra.vector_store import VectorStore

    store = VectorStore(vault_path)
    emb = EmbeddingClient(EMBEDDING_MODEL)
    result = _rl(args["note_path"], vault_path, emb, store, args.get("max_links", 5))
    return json.dumps(result)


def _create_note(args: dict, vault_path: str) -> str:
    folder = _arg(args, "folder", "folder_path", "dir_path")
    fname = _arg(args, "filename", "file_name", "name")
    if not folder and not fname:
        return json.dumps({"error": "Missing folder or filename"})
    if not fname.endswith(".md"):
        fname += ".md"
    content = _arg(args, "content", "text", "body")
    if not content:
        return json.dumps({"error": "Missing content"})
    tags = args.get("tags", [])

    full_dir = _safe_path(vault_path, folder)
    os.makedirs(full_dir, exist_ok=True)
    full_path = os.path.join(full_dir, fname)
    _safe_path(vault_path, os.path.join(folder, fname))

    frontmatter = ""
    if tags:
        frontmatter = "---\ntags:\n" + "\n".join(f"  - {t}" for t in tags) + "\n---\n\n"

    with open(full_path, "w", encoding="utf-8") as f:
        f.write(frontmatter + content)

    rel = os.path.relpath(full_path, vault_path).replace("\\", "/")
    return json.dumps({"created": rel})


def _update_note(args: dict, vault_path: str) -> str:
    note_path = _arg(args, "note_path", "file_path", "path")
    content = _arg(args, "content", "text", "body")
    if not note_path:
        return json.dumps({"error": "Missing note_path"})
    full = _safe_path(vault_path, note_path)
    if not os.path.exists(full):
        return json.dumps({"error": f"File not found: {note_path}"})
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)
    return json.dumps({"updated": note_path})


def _delete_note(args: dict, vault_path: str) -> str:
    note_path = _arg(args, "note_path", "file_path", "path")
    if not note_path:
        return json.dumps({"error": "Missing note_path"})
    full = _safe_path(vault_path, note_path)
    if not os.path.exists(full):
        return json.dumps({"error": f"File not found: {note_path}"})
    trash_dir = os.path.join(vault_path, ".trash")
    os.makedirs(trash_dir, exist_ok=True)
    dest = os.path.join(trash_dir, os.path.basename(note_path))
    os.rename(full, dest)
    return json.dumps({"deleted": note_path, "moved_to": ".trash/"})


def _create_folder(args: dict, vault_path: str) -> str:
    p = _arg(args, "path", "folder", "folder_path", "dir_path")
    if not p:
        return json.dumps({"error": "Missing path"})
    full = _safe_path(vault_path, p)
    os.makedirs(full, exist_ok=True)
    return json.dumps({"created_folder": p})


def _move_note(args: dict, vault_path: str) -> str:
    source = _arg(args, "source", "source_path", "from")
    dest = _arg(args, "destination", "dest_path", "to")
    if not source or not dest:
        return json.dumps({"error": "Missing source or destination"})
    src = _safe_path(vault_path, source)
    dst = _safe_path(vault_path, dest)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    os.rename(src, dst)
    return json.dumps({"moved": source, "to": dest})


async def _ocr_document(args: dict, vault_path: str) -> str:
    file_path = args.get("file_path") or args.get("image_path", "")
    if not os.path.isabs(file_path):
        file_path = os.path.join(vault_path, file_path)
    if not os.path.exists(file_path):
        return json.dumps({"error": f"File not found: {file_path}"})

    output_folder = args.get("output_folder", "OCR")
    stem = Path(file_path).stem

    from app.infra.ocr import extract_text

    try:
        md = await extract_text(file_path)
    except Exception as exc:
        md = f"# {stem}\n\n*OCR failed: {exc}*"

    if not md.strip():
        md = f"# {stem}\n\n*No text extracted from this document.*"

    # Save to vault
    out_dir = _safe_path(vault_path, output_folder)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{stem}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md)

    rel = os.path.relpath(out_path, vault_path).replace("\\", "/")
    return json.dumps({"ocr_result": rel, "characters": len(md)})


def _classify_note(args: dict, vault_path: str) -> str:
    note_path = _arg(args, "note_path", "file_path", "path")
    full = _safe_path(vault_path, note_path)
    if not os.path.exists(full):
        return json.dumps({"error": "File not found"})
    with open(full, encoding="utf-8") as f:
        content = f.read()
    length = len(content)
    has_code = "```" in content or "`" in content
    has_math = "$" in content
    if has_code and has_math:
        category = "technical-note"
    elif has_code:
        category = "code-example"
    elif has_math:
        category = "math-note"
    elif length < 500:
        category = "quick-note"
    elif "学习" in content or "note" in content.lower():
        category = "study-note"
    else:
        category = "general"
    return json.dumps({"path": note_path, "category": category, "length": length})


async def _generate_summary(args: dict, vault_path: str) -> str:
    import app.llm.manager as _lmm
    from app.config import ACTIVE_CHAT_MODEL, ACTIVE_PROVIDER_ID

    note_path = _arg(args, "note_path", "file_path", "path")
    full = _safe_path(vault_path, note_path)
    if not os.path.exists(full):
        return json.dumps({"error": "File not found"})
    with open(full, encoding="utf-8") as f:
        content = f.read()

    if not _lmm.llm_manager:
        return json.dumps({"error": "LLM not available"})

    llm = _lmm.llm_manager.get_chat_client(ACTIVE_PROVIDER_ID, ACTIVE_CHAT_MODEL)
    resp = await llm.async_client.chat.completions.create(
        model=ACTIVE_CHAT_MODEL,
        messages=[
            {"role": "system", "content": "Summarize this note in 2-3 concise paragraphs. Output as Markdown."},
            {"role": "user", "content": content},
        ],
        max_tokens=500,
    )
    summary = resp.choices[0].message.content or ""
    # Append to note
    new_content = content.rstrip() + f"\n\n> **TL;DR:** {summary}\n"
    with open(full, "w", encoding="utf-8") as f:
        f.write(new_content)
    return json.dumps({"summarized": note_path, "summary": summary[:200]})


def _get_vault_status(vault_path: str) -> str:
    from app.infra.indexer import _load_index_state
    from app.infra.vector_store import VectorStore

    state = _load_index_state(vault_path)
    store = VectorStore(vault_path)
    return json.dumps({
        "total_files_indexed": len(state.get("files", {})),
        "total_chunks": store.count(),
        "last_full_index": state.get("last_full_index"),
    })
