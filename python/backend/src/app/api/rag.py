"""RAG query endpoint — vector search + LLM answer with citations."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import app.llm.manager as _llm_mgr
from app.config import ACTIVE_PROVIDER_ID, LLM_MODEL
from app.infra.embedding import EmbeddingClient
from app.infra.vector_store import VectorStore
from app.llm.prompts import TUTOR_SYSTEM_PROMPT
from app.models.rag import RagQueryRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rag", tags=["rag"])

# Injected during startup
embedding_client: EmbeddingClient | None = None
vector_store: VectorStore | None = None


def init_rag(emb: EmbeddingClient, store: VectorStore) -> None:
    global embedding_client, vector_store
    embedding_client = emb
    vector_store = store


async def _rag_stream(
    query: str,
    top_k: int,
    request: Request,
) -> AsyncGenerator[str, None]:
    if not embedding_client or not vector_store:
        yield "data: [DONE]\n\n"
        return

    query_vec = embedding_client.encode_query(query)
    chunks = vector_store.search(query_vec, top_k=top_k)

    if not chunks:
        # No relevant chunks found, fall through to direct chat
        yield "event: source\ndata: []\n\n"

    # Build context
    context_parts: list[str] = []
    for i, c in enumerate(chunks):
        context_parts.append(f"[Source {i + 1}] ({c['note_path']}): {c['content']}")
    context = "\n\n".join(context_parts)

    system_prompt = (
        f"{TUTOR_SYSTEM_PROMPT}\n\n"
        f"Use the following context from the user's notes to answer:\n\n"
        f"{context}\n\n"
        "Cite sources using [Source N] notation. "
        "If the context does not contain the answer, say so and offer a general answer."
    )

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": query},
    ]

    try:
        if not _llm_mgr.llm_manager:
            raise Exception("LLM Manager not initialized")
        rag_client = _llm_mgr.llm_manager.get_chat_client(ACTIVE_PROVIDER_ID, LLM_MODEL)
        stream = await rag_client.async_client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,  # type: ignore[arg-type]
            temperature=0.7,
            max_tokens=2048,
            stream=True,
        )

        last_keepalive = asyncio.get_event_loop().time()

        async for chunk in stream:  # type: ignore[union-attr]
            if await request.is_disconnected():
                return

            now = asyncio.get_event_loop().time()
            if now - last_keepalive > 15:
                yield ": heartbeat\n\n"
                last_keepalive = now

            delta = chunk.choices[0].delta  # type: ignore[union-attr]
            if delta.content:
                payload = json.dumps({"content": delta.content}, ensure_ascii=False)
                yield f"event: token\ndata: {payload}\n\n"

        # Send sources at end
        sources_data = [
            {"note_path": c["note_path"], "content": c["content"][:200], "score": c["score"]}
            for c in chunks
        ]
        yield f"event: source\ndata: {json.dumps(sources_data, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    except asyncio.CancelledError:
        logger.info("RAG stream cancelled.")
    except Exception as exc:
        logger.exception("RAG stream error")
        payload = json.dumps({"message": str(exc)})
        yield f"event: error\ndata: {payload}\n\n"


@router.post("/multi-query")
async def rag_multi_query(
    queries: list[str],
    top_k: int = 5,
) -> dict:
    """Search multiple queries in parallel and merge results.

    Returns deduplicated chunks sorted by score.
    """
    if not embedding_client or not vector_store:
        raise HTTPException(status_code=503, detail="RAG not initialized")

    # Parallel search
    def search_one(q: str) -> list[dict]:
        assert embedding_client and vector_store
        vec = embedding_client.encode_query(q)
        return vector_store.search(vec, top_k=top_k)

    results_per_query = await asyncio.gather(*[asyncio.to_thread(search_one, q) for q in queries])

    # Merge + deduplicate by note_path
    seen: set[str] = set()
    merged: list[dict] = []
    for results in results_per_query:
        for c in results:
            key = c.get("note_path", "") + c.get("content", "")[:50]
            if key not in seen:
                seen.add(key)
                merged.append(c)

    merged.sort(key=lambda c: c.get("score", 0), reverse=True)

    return {
        "queries": len(queries),
        "results": [
            {"note_path": c["note_path"], "content": c["content"][:300], "score": c["score"]}
            for c in merged[:top_k * 2]
        ],
    }


@router.post("/query")
async def rag_query(request: Request, body: RagQueryRequest) -> StreamingResponse:
    if not embedding_client or not vector_store:
        raise HTTPException(
            status_code=503, detail="RAG service not initialized (no vault indexed)"
        )

    return StreamingResponse(
        _rag_stream(body.query, body.top_k, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
