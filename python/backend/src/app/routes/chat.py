"""Chat completion route with SSE streaming."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.config import ACTIVE_CHAT_MODEL, ACTIVE_PROVIDER_ID, LLM_MODEL, REASONING_EFFORT, REASONING_ENABLED
from app.models.chat import ChatRequest
import app.services.llm_manager as _llm_mgr

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


async def _stream_chat(
    messages: list[dict[str, Any]],
    model: str,
    temperature: float,
    max_tokens: int,
    request: Request,
) -> AsyncGenerator[str, None]:
    """Yield SSE-formatted strings for the chat completion stream."""
    try:
        if not _llm_mgr.llm_manager:
            raise Exception("LLM Manager not initialized")
        chat_client = _llm_mgr.llm_manager.get_chat_client(ACTIVE_PROVIDER_ID, model or LLM_MODEL)
        extra: dict = {}
        if REASONING_ENABLED:
            extra["extra_body"] = {"thinking": {"type": "enabled"}}  # type: ignore[assignment]
        stream = await chat_client.async_client.chat.completions.create(
            model=model or LLM_MODEL,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature,
            max_tokens=max_tokens,
            reasoning_effort=REASONING_EFFORT,  # type: ignore[arg-type]
            stream=True,
            **extra,  # type: ignore[arg-type]
        )  # type: ignore[call-overload]

        last_keepalive = asyncio.get_event_loop().time()

        async for chunk in stream:  # type: ignore[union-attr]
            if await request.is_disconnected():
                logger.info("Client disconnected; aborting stream.")
                return

            now = asyncio.get_event_loop().time()
            if now - last_keepalive > 15:
                yield ": heartbeat\n\n"
                last_keepalive = now

            delta = chunk.choices[0].delta  # type: ignore[union-attr]
            if getattr(delta, "reasoning_content", None):
                payload = json.dumps({"content": delta.reasoning_content}, ensure_ascii=False)  # type: ignore[union-attr]
                yield f"event: thinking\ndata: {payload}\n\n"
            if delta.content:
                payload = json.dumps({"content": delta.content}, ensure_ascii=False)
                yield f"event: token\ndata: {payload}\n\n"

            if delta.role:
                payload = json.dumps({"role": delta.role})
                yield f"event: role\ndata: {payload}\n\n"

        yield "data: [DONE]\n\n"

    except asyncio.CancelledError:
        logger.info("Stream cancelled.")
    except Exception as exc:
        logger.exception("Stream error")
        payload = json.dumps({"message": str(exc)})
        yield f"event: error\ndata: {payload}\n\n"


@router.post("/stream")
async def chat_stream(request: Request, body: ChatRequest) -> StreamingResponse:
    """Stream a chat completion via Server-Sent Events."""
    try:
        messages: list[dict[str, Any]] = [
            {"role": m.role, "content": m.content} for m in body.messages
        ]
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid messages: {exc}") from exc

    return StreamingResponse(
        _stream_chat(
            messages=messages,
            model=body.model or LLM_MODEL,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
            request=request,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
