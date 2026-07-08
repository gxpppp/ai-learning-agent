"""BGE-M3 embedding client via sentence-transformers.

BGE-M3 produces 1024-dim dense vectors + sparse lexical weights.
Supports 100+ languages including Chinese and English.
"""

from __future__ import annotations

from sentence_transformers import SentenceTransformer

MODEL_NAME = "BAAI/bge-m3"


class EmbeddingClient:
    def __init__(self, model_name: str = MODEL_NAME) -> None:
        self.model = SentenceTransformer(model_name)

    def encode(self, texts: list[str]) -> list[list[float]]:
        embeddings = self.model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [emb.tolist() for emb in embeddings]

    def encode_query(self, text: str) -> list[float]:
        embedding = self.model.encode(
            text,
            normalize_embeddings=True,
            prompt_name="query",
        )
        return embedding.tolist()

    @property
    def dimension(self) -> int:
        return self.model.get_sentence_embedding_dimension()
