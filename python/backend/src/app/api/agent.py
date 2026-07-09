"""Agent chat endpoint — routes simple tasks to JSON plan parser, complex to Gateway."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import app.llm.manager as _llm_mgr
from app.config import ACTIVE_CHAT_MODEL, ACTIVE_PROVIDER_ID, OBSIDIAN_VAULT_PATH, TOOL_PERMISSIONS
from app.core.dispatcher import TaskComplexity, classify
from app.core.event_bus import (
    done_event,
    error_event,
    format_sse,
    heartbeat,
    token_event,
    tool_call_event,
    tool_result_event,
)
from app.core.tool_registry import execute_tool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["agent"])

AGENT_PROMPT = """You are an AI learning assistant with full control over the user's Obsidian vault.

Available tools:

{tools_list}

When the user asks you to do something, first explain your plan briefly,
then output a JSON action block wrapped in ```json fences:

```json
{{
  "actions": [
    {{"tool": "read_note", "args": {{"note_path": "Notes/example.md"}}}},
    {{"tool": "create_note", "args": {{"folder": "Output", "filename": "summary.md", "content": "..."}}}}
  ],
  "summary": "Brief explanation of what you'll do"
}}
```

Rules:
- Use the right tools in the right order
- Only use tools listed above
- For simple chats that need no tools, just reply normally — no JSON needed
- After executing actions, summarize what was done

The vault is at: {vault_path}
Permission mode: {permission_mode}
"""


async def _agent_loop(
    user_message: str,
    conversation: list[dict[str, Any]],
    request: Request,
) -> AsyncGenerator[str, None]:
    if not _llm_mgr.llm_manager:
        yield error_event("LLM Manager not initialized")
        return

    # ── Gateway routing ──
    complexity = classify(user_message)

    if complexity == TaskComplexity.SEARCH:
        from app.gateway.router import route
        async for event in route(user_message, OBSIDIAN_VAULT_PATH, conversation):
            if await request.is_disconnected():
                return
            yield event
        yield done_event()
        return

    if complexity == TaskComplexity.COMPLEX:
        # Use OpenHarness-powered gateway coordinator
        from app.gateway.coordinator import GatewayCoordinator
        from app.gateway.router import route as gateway_route

        # First, let the router set up context (agent_start etc.)
        async for event in gateway_route(user_message, OBSIDIAN_VAULT_PATH, conversation):
            if await request.is_disconnected():
                return
            yield event

        # Then, use OpenHarness engine for the actual work
        coordinator = GatewayCoordinator(
            vault_path=OBSIDIAN_VAULT_PATH,
            permission_mode=TOOL_PERMISSIONS,
        )

        # Build system prompt with tool list
        from app.core.tool_registry import get_tools
        tools = get_tools(TOOL_PERMISSIONS)
        tools_list = "\n".join(
            f"- **{t['function']['name']}**: {t['function']['description']}"
            for t in tools
        )
        system_prompt = AGENT_PROMPT.format(
            tools_list=tools_list,
            vault_path=OBSIDIAN_VAULT_PATH,
            permission_mode=TOOL_PERMISSIONS,
        )

        async for event in coordinator.execute(
            user_message=user_message,
            system_prompt=system_prompt,
            provider_id=ACTIVE_PROVIDER_ID,
            model=ACTIVE_CHAT_MODEL,
        ):
            if await request.is_disconnected():
                return
            yield event
        return

    # ── Simple path: JSON action plan ──
    from app.core.tool_registry import get_tools

    tools = get_tools(TOOL_PERMISSIONS)
    tools_list = "\n".join(
        f"- **{t['function']['name']}**: {t['function']['description']}"
        for t in tools
    )

    system_prompt = AGENT_PROMPT.format(
        tools_list=tools_list,
        vault_path=OBSIDIAN_VAULT_PATH,
        permission_mode=TOOL_PERMISSIONS,
    )

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        *conversation,
        {"role": "user", "content": user_message},
    ]

    client = _llm_mgr.llm_manager.get_chat_client(ACTIVE_PROVIDER_ID, ACTIVE_CHAT_MODEL)

    try:
        response = await client.async_client.chat.completions.create(
            model=ACTIVE_CHAT_MODEL,
            messages=messages,  # type: ignore[arg-type]
            temperature=0.7,
            stream=False,
        )  # type: ignore[call-overload]
    except Exception as exc:
        logger.exception("Agent LLM call failed")
        yield error_event(str(exc))
        return

    if await request.is_disconnected():
        return

    choice = response.choices[0]  # type: ignore[union-attr]
    msg = choice.message

    if getattr(msg, "reasoning_content", None):
        yield format_sse("thinking", {"content": msg.reasoning_content})  # type: ignore[union-attr]

    full_text = msg.content or ""

    actions = _parse_actions(full_text)

    if actions:
        visible_text = _strip_json_blocks(full_text).strip()
        if visible_text:
            yield token_event(visible_text)
            yield token_event("\n\n")

        for i, action in enumerate(actions):
            tool_name = action.get("tool", "")
            tool_args = action.get("args", {})

            yield tool_call_event(f"local_{i}", tool_name, tool_args)

            t0 = asyncio.get_event_loop().time()
            result = await execute_tool(tool_name, tool_args, OBSIDIAN_VAULT_PATH)
            elapsed = round((asyncio.get_event_loop().time() - t0) * 1000)

            yield tool_result_event(f"local_{i}", tool_name, result, elapsed)

        yield token_event(f"\nDone \u2014 {len(actions)} action(s) completed.")
    else:
        yield token_event(full_text)

    yield done_event()


def _parse_actions(text: str) -> list[dict[str, Any]]:
    """Extract JSON action plan from LLM response."""
    matches = re.findall(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    for match in matches:
        try:
            data = json.loads(match.strip())
            actions = data.get("actions", data.get("plan", []))
            if isinstance(actions, list) and actions:
                return actions
        except json.JSONDecodeError:
            continue
    return []


def _strip_json_blocks(text: str) -> str:
    """Remove JSON code fences from text for display."""
    return re.sub(r"```(?:json)?\s*\n?.*?\n?```", "", text, flags=re.DOTALL)


class AgentChatRequest(BaseModel):
    content: str
    conversation: list[dict[str, Any]] = []


@router.post("/chat")
async def agent_chat(request: Request, body: AgentChatRequest) -> StreamingResponse:
    if not OBSIDIAN_VAULT_PATH:
        raise HTTPException(status_code=400, detail="Vault path not configured")

    async def stream_with_heartbeat() -> AsyncGenerator[str, None]:
        """Wrap agent loop with periodic heartbeat to keep SSE alive."""
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
