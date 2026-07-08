"""Agent chat endpoint — SSE streaming with tool-calling loop.

The Agent autonomously decides whether to call tools or respond directly.
Each tool call is streamed to the client and executed server-side.
Results are fed back into the LLM context for multi-step reasoning.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.config import ACTIVE_AGENT_MODEL, ACTIVE_PROVIDER_ID, OBSIDIAN_VAULT_PATH, REASONING_EFFORT, REASONING_ENABLED, TOOL_PERMISSIONS
import app.services.llm_manager as _llm_mgr
from app.services.tool_registry import execute_tool, get_tools
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["agent"])

AGENT_SYSTEM_PROMPT = """You are an AI learning assistant with full control over the user's Obsidian vault.

You have access to tools that let you search, read, create, organize, and analyze notes.
When the user asks you to do something, use the appropriate tools to accomplish it.

Guidelines:
1. Be proactive: if the user says "organize my notes", figure out what needs organizing.
2. Be transparent: explain what you're doing before and after tool calls.
3. Be efficient: chain tool calls when you need multiple pieces of information.
4. Be helpful: after completing a task, summarize what you did and ask if they need more.

The vault path is: {vault_path}
Permission mode: {permission_mode}
"""


async def _agent_loop(
    user_message: str,
    conversation: list[dict[str, Any]],
    request: Request,
) -> AsyncGenerator[str, None]:
    if not _llm_mgr.llm_manager:
        yield _sse("error", {"message": "LLM Manager not initialized"})
        return

    tools = get_tools(TOOL_PERMISSIONS)
    system_prompt = AGENT_SYSTEM_PROMPT.format(
        vault_path=OBSIDIAN_VAULT_PATH,
        permission_mode=TOOL_PERMISSIONS,
    )

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        *conversation,
        {"role": "user", "content": user_message},
    ]

    client = _llm_mgr.llm_manager.get_chat_client(ACTIVE_PROVIDER_ID, ACTIVE_AGENT_MODEL)

    max_iterations = 8
    for _iter in range(max_iterations):
        if await request.is_disconnected():
            return

        try:
            extra: dict = {}
            if REASONING_ENABLED:
                extra["extra_body"] = {"thinking": {"type": "enabled"}}  # type: ignore[assignment]
            response = await client.async_client.chat.completions.create(
                model=ACTIVE_AGENT_MODEL,
                messages=messages,  # type: ignore[arg-type]
                tools=tools,  # type: ignore[arg-type]
                reasoning_effort=REASONING_EFFORT,  # type: ignore[arg-type]
                stream=False,
                **extra,  # type: ignore[arg-type]
            )  # type: ignore[call-overload]
        except Exception as exc:
            logger.exception("Agent LLM call failed")
            yield _sse("error", {"message": str(exc)})
            return

        choice = response.choices[0]  # type: ignore[union-attr]
        msg = choice.message

        # If the model wants to call tools
        if msg.tool_calls:
            for tc in msg.tool_calls:
                tool_name = tc.function.name  # type: ignore[union-attr]
                try:
                    tool_args = json.loads(tc.function.arguments)  # type: ignore[union-attr]
                except json.JSONDecodeError:
                    tool_args = {}

                yield _sse("tool_call", {
                    "id": tc.id,
                    "name": tool_name,
                    "args": tool_args,
                })

                t0 = asyncio.get_event_loop().time()
                result = await execute_tool(tool_name, tool_args, OBSIDIAN_VAULT_PATH)
                elapsed = round((asyncio.get_event_loop().time() - t0) * 1000)

                yield _sse("tool_result", {
                    "id": tc.id,
                    "name": tool_name,
                    "content": result,
                    "elapsed_ms": elapsed,
                })

                messages.append({"role": "assistant", "tool_calls": [tc]})
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

            # Continue loop — LLM will see tool results and decide next action
            continue

        # Regular text response
        if getattr(msg, "reasoning_content", None):
            yield _sse("thinking", {"content": msg.reasoning_content})
        if msg.content:
            yield _sse("token", {"content": msg.content})
        asst_msg: dict[str, Any] = {"role": "assistant", "content": msg.content}
        if getattr(msg, "reasoning_content", None):
            asst_msg["reasoning_content"] = msg.reasoning_content
        messages.append(asst_msg)
        break

    yield "data: [DONE]\n\n"


def _sse(event: str, data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


class AgentChatRequest(BaseModel):
    content: str
    conversation: list[dict[str, Any]] = []


@router.post("/chat")
async def agent_chat(request: Request, body: AgentChatRequest) -> StreamingResponse:
    if not OBSIDIAN_VAULT_PATH:
        raise HTTPException(status_code=400, detail="Vault path not configured")

    return StreamingResponse(
        _agent_loop(body.content, body.conversation, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
