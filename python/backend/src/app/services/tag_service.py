"""Tag suggestion and bidirectional link recommendation service."""

from __future__ import annotations

import logging
import os
from typing import Any

import frontmatter

from app.services.embedding import EmbeddingClient
from app.services.vector_store import VectorStore

logger = logging.getLogger(__name__)


def _read_note_text(note_path: str, vault_path: str) -> str:
    full_path = os.path.join(vault_path, note_path)
    with open(full_path, encoding="utf-8") as f:
        raw = f.read()
    if raw.startswith("---"):
        end = raw.find("---", 3)
        if end != -1:
            return raw[end + 3 :].strip()
    return raw


def _read_existing_tags(note_path: str, vault_path: str) -> list[str]:
    full_path = os.path.join(vault_path, note_path)
    try:
        post = frontmatter.load(full_path)
        tags = post.get("tags", [])
        if isinstance(tags, str):
            return [t.strip() for t in tags.split(",")]
        if isinstance(tags, list):
            return [str(t) for t in tags]
    except Exception as e:
        logger.warning("Failed to read existing tags for %s: %s", note_path, e)
    return []


def suggest_tags(
    note_path: str,
    vault_path: str,
    embedding: EmbeddingClient,
    store: VectorStore,
    max_tags: int = 5,
) -> dict[str, Any]:
    """Suggest tags for a note based on content similarity and keywords."""
    text = _read_note_text(note_path, vault_path)
    if not text.strip():
        return {"tags": [], "confidence": 0.0}

    # Keyword extraction via TF-IDF on the note itself
    from sklearn.feature_extraction.text import TfidfVectorizer

    try:
        vectorizer = TfidfVectorizer(max_features=max_tags * 3, stop_words="english")
        vectorizer.fit_transform([text])
        keywords = [
            w for w, s in sorted(
                zip(vectorizer.get_feature_names_out(), vectorizer.idf_),
                key=lambda x: x[1],
                reverse=True,
            )
        ]
        # Filter to meaningful tags
        tags = [kw for kw in keywords[:max_tags] if len(kw) > 1 and not kw.isdigit()]
    except Exception as e:
        logger.warning("TF-IDF tag extraction failed for %s: %s", note_path, e)
        tags = []

    return {"tags": tags[:max_tags], "confidence": min(0.9, len(tags) / max_tags)}


def recommend_links(
    note_path: str,
    vault_path: str,
    embedding: EmbeddingClient,
    store: VectorStore,
    max_links: int = 5,
) -> dict[str, Any]:
    """Recommend bidirectional links to related notes."""
    text = _read_note_text(note_path, vault_path)
    if not text.strip():
        return {"links": []}

    query_vec = embedding.encode_query(text)
    results = store.search(query_vec, top_k=max_links + 1)

    links = []
    for r in results:
        if r["note_path"] == note_path:
            continue
        excerpt = r["content"][:200].replace("\n", " ")
        links.append(
            {
                "target": r["note_path"],
                "context": excerpt,
                "score": round(r["score"], 4),
            }
        )

    return {"links": links[:max_links]}
