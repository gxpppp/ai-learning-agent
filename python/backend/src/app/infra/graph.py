"""Knowledge graph generator — produces D3-force compatible graph data.

Nodes: notes (by path)
Edges: wiki links [[target]] and semantic similarity links
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections import Counter
from pathlib import Path

logger = logging.getLogger(__name__)

WIKI_LINK_RE = re.compile(r"\[\[([^\]|#]+)(?:[|#][^\]]+)?\]\]")


def generate_graph(vault_path: str, folder: str | None = None, max_nodes: int = 100) -> dict:
    """Generate knowledge graph data from vault notes.

    Returns a dict with {nodes: [...], links: [...]} for D3-force layout.
    """
    nodes: dict[str, dict] = {}
    links: list[dict] = []
    link_counter: Counter = Counter()

    # Scan vault for markdown files
    search_dir = os.path.join(vault_path, folder) if folder else vault_path
    if not os.path.isdir(search_dir):
        return {"nodes": [], "links": []}

    md_files = _find_md_files(search_dir, vault_path)

    # Build nodes
    for rel_path in md_files[:max_nodes]:
        node_id = rel_path
        name = Path(rel_path).stem
        parent = str(Path(rel_path).parent) if Path(rel_path).parent != Path(".") else ""
        size = os.path.getsize(os.path.join(vault_path, rel_path))

        # Check for tags in frontmatter
        tags = _extract_tags(os.path.join(vault_path, rel_path))
        group = tags[0] if tags else _classify_group(rel_path)

        nodes[node_id] = {
            "id": node_id,
            "name": name,
            "group": group,
            "size": min(size // 100, 50) + 3,
            "tags": tags,
            "parent": parent,
        }

    # Build links from wiki links
    for rel_path, node in list(nodes.items()):
        content = _read_file(os.path.join(vault_path, rel_path))
        for target in WIKI_LINK_RE.findall(content):
            # Normalize target path
            if not target.endswith(".md"):
                target += ".md"
            # Resolve relative to current file's directory
            target_path = str(Path(Path(rel_path).parent) / target).replace("\\", "/")
            if target_path in nodes:
                key = f"{node['id']}->{target_path}"
                link_counter[key] += 1

    # Add links (top N by weight)
    for key, weight in link_counter.most_common(max_nodes * 3):
        source, target = key.split("->", 1)
        links.append({"source": source, "target": target, "value": weight})

    return {
        "nodes": list(nodes.values()),
        "links": links,
        "total_notes": len(md_files),
    }


def _find_md_files(search_dir: str, vault_path: str) -> list[str]:
    """Find all .md files relative to vault root."""
    files = []
    skip_dirs = {".obsidian", ".ai-tutor", ".trash", ".git", "node_modules"}
    for root, dirs, filenames in os.walk(search_dir):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for fname in filenames:
            if fname.endswith(".md"):
                full = os.path.join(root, fname)
                rel = os.path.relpath(full, vault_path).replace("\\", "/")
                files.append(rel)
    return sorted(files)


def _extract_tags(filepath: str) -> list[str]:
    """Extract tags from YAML frontmatter."""
    try:
        with open(filepath, encoding="utf-8") as f:
            content = f.read()
        if content.startswith("---"):
            end = content.find("---", 3)
            if end > 0:
                fm = content[3:end]
                tags = []
                for line in fm.split("\n"):
                    stripped = line.strip()
                    if stripped.startswith("tags:") or stripped.startswith("- "):
                        tag = stripped.lstrip("- ").strip()
                        if tag and not tag.startswith("tags:"):
                            tag = tag.lstrip("tags:").strip()
                            if tag:
                                tags.append(tag)
                return tags
    except Exception:
        pass
    return []


def _classify_group(rel_path: str) -> str:
    """Classify a note into a group based on path."""
    parts = Path(rel_path).parts
    if len(parts) > 1:
        return parts[0]
    return "root"


def _read_file(filepath: str) -> str:
    """Read file content safely."""
    try:
        with open(filepath, encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""
