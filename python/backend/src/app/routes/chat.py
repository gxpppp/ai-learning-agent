"""Chat completion route with SSE streaming."""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.config import LLM_MODEL
from app.models.chat import ChatRequest
from app.services.llm_client import client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


async def _stream_chat(
    messages: list[dict[str, str]],
    model: str,
    temperature: float,
    max_tokens: int,
    request: Request,
):
    """Yield SSE-formatted strings for the chat completion stream."""
    try:
        stream = await client.async_client.chat.completions.create(
            model=model or LLM_MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        last_keepalive = asyncio.get_event_loop().time()

        async for chunk in stream:
            if await request.is_disconnected():
                logger.info("Client disconnected; aborting stream.")
                return

            now = asyncio.get_event_loop().time()
            if now - last_keepalive > 15:
                yield ": heartbeat\n\n"
                last_keepalive = now

            delta = chunk.choices[0].delta
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
async def chat_stream(request: Request, body: ChatRequest):
    """Stream a chat completion via Server-Sent Events."""
    try:
        messages = [{"role": m.role, "content": m.content} for m in body.messages]
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
