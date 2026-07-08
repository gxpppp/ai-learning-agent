"""LanceDB vector store wrapper.

Embedded mode — no server, runs in-process with FastAPI.
Stores document chunks with their embeddings and metadata.
Supports hybrid search: vector similarity + full-text.
"""

from __future__ import annotations

import logging
import os

import lancedb
import pyarrow as pa

logger = logging.getLogger(__name__)

DB_TABLE_NAME = "chunks"

_schema = pa.schema(
    [
        pa.field("id", pa.string()),
        pa.field("note_path", pa.string()),
        pa.field("content", pa.string()),
        pa.field("vector", pa.list_(pa.float32(), list_size=1024)),
        pa.field("chunk_index", pa.int32()),
        pa.field("total_chunks", pa.int32()),
    ]
)


class VectorStore:
    def __init__(self, vault_path: str) -> None:
        db_dir = os.path.join(vault_path, ".ai-tutor", "lancedb")
        os.makedirs(db_dir, exist_ok=True)
        self.db = lancedb.connect(db_dir)
        self._ensure_table()

    def _ensure_table(self) -> None:
        if DB_TABLE_NAME not in self.db.table_names():
            self.db.create_table(DB_TABLE_NAME, schema=_schema)

    @property
    def table(self) -> lancedb.table.Table:
        return self.db.open_table(DB_TABLE_NAME)

    def count(self) -> int:
        return self.table.count_rows()

    def search(self, query_vector: list[float], top_k: int = 5) -> list[dict]:
        results = (
            self.table.search(query_vector)
            .metric("cosine")
            .limit(top_k)
            .to_list()
        )
        return [
            {
                "note_path": r["note_path"],
                "content": r["content"],
                "score": float(r["_distance"]),
            }
            for r in results
        ]

    def hybrid_search(
        self, query_vector: list[float], query_text: str, top_k: int = 5
    ) -> list[dict]:
        # Vector search first, then text-based rerank
        results = (
            self.table.search(query_vector)
            .metric("cosine")
            .limit(top_k * 3)
            .to_list()
        )
        # Client-side text filter: boost chunks containing query terms
        query_terms = set(query_text.lower().split())
        scored: list[dict] = []
        for r in results:
            content_lower = r["content"].lower()
            matches = sum(1 for t in query_terms if t in content_lower)
            boost = 1.0 + matches * 0.1
            scored.append(
                {
                    "note_path": r["note_path"],
                    "content": r["content"],
                    "score": round(float(r["_distance"]) / boost, 4),
                }
            )
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def add_chunks(self, records: list[dict]) -> None:
        rows = []
        for r in records:
            rows.append(
                {
                    "id": r["id"],
                    "note_path": r["note_path"],
                    "content": r["content"],
                    "vector": r["vector"],
                    "chunk_index": r["chunk_index"],
                    "total_chunks": r.get("total_chunks", 1),
                }
            )
        self.table.add(rows)

    def delete_by_note(self, note_path: str) -> None:
        escaped = note_path.replace("'", "''")
        try:
            self.table.delete(f"note_path = '{escaped}'")
        except Exception as e:
            logger.warning("Failed to delete chunks for %s: %s", note_path, e)

    def clear(self) -> None:
        self.db.drop_table(DB_TABLE_NAME)
        self._ensure_table()
