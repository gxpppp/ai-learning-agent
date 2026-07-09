"""Agent chat endpoint — all requests through OpenHarness QueryEngine for interleaved text+tool execution."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import app.llm.manager as _llm_mgr
from app.config import ACTIVE_CHAT_MODEL, ACTIVE_PROVIDER_ID, OBSIDIAN_VAULT_PATH, TOOL_PERMISSIONS
from app.core.event_bus import (
    done_event,
    error_event,
    heartbeat,
)
from app.core.logging import new_trace_id

logger = logging.getLogger(__name__)
tracer = logging.getLogger("agent")

router = APIRouter(prefix="/api/agent", tags=["agent"])


async def _agent_loop(
    user_message: str,
    conversation: list[dict[str, Any]],
    request: Request,
) -> AsyncGenerator[str, None]:
    trace_id = new_trace_id()
    tracer.info("request", extra={
        "trace_id": trace_id,
        "input": user_message[:100],
        "vault": OBSIDIAN_VAULT_PATH[:50],
    })

    if not _llm_mgr.llm_manager:
        yield error_event("LLM Manager not initialized")
        return

    # Build system prompt describing available tools
    from app.core.tool_registry import get_tools
    tools = get_tools(TOOL_PERMISSIONS)
    tools_list = "\n".join(
        f"- **{t['function']['name']}**: {t['function']['description']}"
        for t in tools
    )
    system_prompt = (
        "You are an AI assistant with direct control over the user's Obsidian vault.\n\n"
        "Available tools:\n\n"
        f"{tools_list}\n\n"
        "Use tools directly when you need to. Explain what you are doing as you go.\n"
        "Call tools while you talk — do not wait until the end.\n"
        f"The vault is at: {OBSIDIAN_VAULT_PATH}\n"
        f"Permission mode: {TOOL_PERMISSIONS}\n"
    )

    # All requests through OpenHarness engine (interleaved text + tools)
    from app.gateway.coordinator import GatewayCoordinator
    coordinator = GatewayCoordinator(
        vault_path=OBSIDIAN_VAULT_PATH,
        permission_mode=TOOL_PERMISSIONS,
    )

    async for event in coordinator.execute(
        user_message=user_message,
        system_prompt=system_prompt,
        provider_id=ACTIVE_PROVIDER_ID,
        model=ACTIVE_CHAT_MODEL,
        conversation=conversation,
    ):
        if await request.is_disconnected():
            return
        yield event


class AgentChatRequest(BaseModel):
    content: str
    conversation: list[dict[str, Any]] = []


@router.post("/chat")
async def agent_chat(request: Request, body: AgentChatRequest) -> StreamingResponse:
    if not OBSIDIAN_VAULT_PATH:
        raise HTTPException(status_code=400, detail="Vault path not configured")

    async def stream_with_heartbeat() -> AsyncGenerator[str, None]:
        gen = _agent_loop(body.content, body.conversation, request)
        while True:
            try:
                next_val = await asyncio.wait_for(gen.__anext__(), timeout=15)
                yield next_val
            except asyncio.TimeoutError:
                if await request.is_disconnected():
                    return
                yield heartbeat()
            except StopAsyncIteration:
                return

    return StreamingResponse(
        stream_with_heartbeat(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
