"""BGE-M3 embedding service — FastAPI server with sentence-transformers.

Endpoints:
  POST /embed       {"texts": ["hello", "world"]}     → [[1024], [1024]]
  POST /embed_query {"text": "query"}                  → [1024]
  GET  /health                                         → {"status":"ok","model":"BAAI/bge-m3","dim":1024}
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="[embedding] %(message)s")
logger = logging.getLogger("embedding")

_model = None


class EmbedRequest(BaseModel):
    texts: list[str]


class EmbedQueryRequest(BaseModel):
    text: str


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    global _model
    from sentence_transformers import SentenceTransformer
    _model = SentenceTransformer("BAAI/bge-m3")
    logger.info("BGE-M3 loaded — dim=%d", _model.get_sentence_embedding_dimension())
    yield

app = FastAPI(title="BGE-M3 Embedding", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "model": "BAAI/bge-m3", "dim": 1024}


@app.post("/embed")
async def embed(body: EmbedRequest):
    if not _model:
        raise HTTPException(503, "Model not loaded")
    vecs = _model.encode(body.texts, normalize_embeddings=True)
    return {"vectors": [v.tolist() for v in vecs]}


@app.post("/embed_query")
async def embed_query(body: EmbedQueryRequest):
    if not _model:
        raise HTTPException(503, "Model not loaded")
    vec = _model.encode(body.text, prompt="Represent this query for retrieval:", normalize_embeddings=True)
    return {"vector": vec.tolist()}
