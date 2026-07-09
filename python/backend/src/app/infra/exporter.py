"""Document exporter — generate VitePress-compatible docs from vault notes."""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

WIKI_LINK_RE = re.compile(r"\[\[([^\]|#]+)(?:[|#][^\]]+)?\]\]")


def export_to_markdown(
    vault_path: str,
    output_dir: str,
    folder: str | None = None,
    include_tags: list[str] | None = None,
) -> dict:
    """Export vault notes as a VitePress-compatible docs site.

    Each note becomes a .md file in the output directory.
    Wiki links are converted to relative markdown links.
    """
    source_dir = os.path.join(vault_path, folder) if folder else vault_path
    if not os.path.isdir(source_dir):
        return {"error": "Source folder not found", "exported": 0}

    skip_dirs = {".obsidian", ".ai-tutor", ".trash", ".git", "node_modules"}
    exported = 0
    sidebar_items: list[dict] = []

    os.makedirs(output_dir, exist_ok=True)

    # Write .vitepress/config.js
    _write_config(output_dir)

    # Process notes
    for root, dirs, filenames in os.walk(source_dir):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for fname in sorted(filenames):
            if not fname.endswith(".md"):
                continue

            full_path = os.path.join(root, fname)
            rel_path = os.path.relpath(full_path, source_dir).replace("\\", "/")

            try:
                with open(full_path, encoding="utf-8") as f:
                    content = f.read()

                # Skip if tag filter active
                if include_tags:
                    tags = _extract_frontmatter_tags(content)
                    if not any(t in include_tags for t in tags):
                        continue

                # Convert wiki links to MD links
                content = _convert_wiki_links(content, source_dir, root)

                # Write output
                out_path = os.path.join(output_dir, rel_path)
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(content)

                sidebar_items.append({
                    "text": Path(fname).stem,
                    "link": "/" + rel_path.replace(".md", ""),
                })
                exported += 1

            except Exception:
                logger.exception(f"Failed to export: {rel_path}")

    # Write sidebar
    _write_sidebar(output_dir, sidebar_items)
    _write_index(output_dir, exported)

    return {"exported": exported, "output_dir": output_dir}


def _extract_frontmatter_tags(content: str) -> list[str]:
    """Extract tags from frontmatter."""
    if not content.startswith("---"):
        return []
    end = content.find("---", 3)
    if end <= 0:
        return []
    fm = content[3:end]
    tags = []
    for line in fm.split("\n"):
        stripped = line.strip()
        if stripped.startswith("tags:") or stripped.startswith("- "):
            tag = stripped.lstrip("- tags:").lstrip("- ").strip()
            if tag:
                tags.append(tag)
    return tags


def _convert_wiki_links(content: str, source_dir: str, current_dir: str) -> str:
    """Convert [[wiki links]] to [text](relative/path.md) format."""
    def _replace(m: re.Match) -> str:
        target = m.group(1)
        text = m.group(2) if m.group(2) else target
        if target.endswith(".md"):
            link_target = target
        else:
            link_target = target + ".md"

        try:
            rel_to_source = os.path.relpath(
                os.path.join(current_dir, link_target), source_dir
            ).replace("\\", "/")
        except ValueError:
            return f"[{text}]({target})"

        if "#" in link_target:
            base, anchor = link_target.rsplit("#", 1)
            try:
                rel_base = os.path.relpath(
                    os.path.join(current_dir, base), source_dir
                ).replace("\\", "/")
                return f"[{text}]({rel_base}#{anchor})"
            except ValueError:
                return f"[{text}]({link_target})"

        return f"[{text}]({rel_to_source})"

    return re.sub(r"\[\[([^\]|#]+)(?:[|#]([^\]]+))?\]\]", _replace, content)


def _write_config(output_dir: str) -> None:
    """Write VitePress config."""
    config_dir = os.path.join(output_dir, ".vitepress")
    os.makedirs(config_dir, exist_ok=True)
    config = f"""\
export default {{
  title: "Vault Docs",
  description: "Knowledge base exported from Obsidian",
  themeConfig: {{
    sidebar: [],
    nav: [{{ text: "Home", link: "/" }}],
  }},
}}
"""
    with open(os.path.join(config_dir, "config.js"), "w", encoding="utf-8") as f:
        f.write(config)


def _write_sidebar(output_dir: str, items: list[dict]) -> None:
    """Write sidebar JSON for the config."""
    sidebar_path = os.path.join(output_dir, ".vitepress", "sidebar.json")
    with open(sidebar_path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def _write_index(output_dir: str, total: int) -> None:
    """Write the index.md home page."""
    index = f"""---
home: true
heroText: Vault Docs
tagline: {total} notes exported from your Obsidian vault
---

Browse the sidebar to explore your knowledge base.
"""
    with open(os.path.join(output_dir, "index.md"), "w", encoding="utf-8") as f:
        f.write(index)
