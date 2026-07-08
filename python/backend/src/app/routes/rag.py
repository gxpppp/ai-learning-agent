"""RAG query endpoint — vector search + LLM answer with citations."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncGenerator, Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.config import LLM_MODEL
from app.models.rag import RagQueryRequest
from app.services.embedding import EmbeddingClient
from app.services.llm_client import client
from app.services.vector_store import VectorStore

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
        "You are an AI tutor with access to the user's personal knowledge base. "
        "Use the provided context to answer the question. "
        "Cite sources using [Source N] notation. "
        "If the context does not contain the answer, say so and offer a general answer.\n\n"
        f"Context:\n{context}"
    )

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": query},
    ]

    try:
        stream = await client.async_client.chat.completions.create(
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
