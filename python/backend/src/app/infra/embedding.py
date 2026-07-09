"""BGE-M3 embedding service — HTTP client for Docker-hosted embedding API."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class EmbeddingClient:
    """HTTP client for the Docker-hosted BGE-M3 embedding service."""

    def __init__(self, server_url: str = "http://127.0.0.1:8081"):
        self._server_url = server_url.rstrip("/")
        self._dimension: int | None = None

    @property
    def dimension(self) -> int:
        if self._dimension is None:
            self._dimension = 1024  # BGE-M3 default
        return self._dimension

    def encode(self, texts: list[str]) -> list[list[float]]:
        """Encode a batch of texts to embeddings."""
        import httpx
        try:
            r = httpx.post(
                f"{self._server_url}/embed",
                json={"texts": texts},
                timeout=60,
            )
            r.raise_for_status()
            return r.json()["vectors"]
        except Exception:
            logger.exception("Embedding API call failed")
            raise

    def encode_query(self, text: str) -> list[float]:
        """Encode a single query with BGE-M3 query prompt."""
        import httpx
        try:
            r = httpx.post(
                f"{self._server_url}/embed_query",
                json={"text": text},
                timeout=30,
            )
            r.raise_for_status()
            return r.json()["vector"]
        except Exception:
            logger.exception("Embedding query API call failed")
            raise
