"""Agent chat endpoint — LLM produces JSON action plan, tools execute locally.

No function calling API required. LLM returns a JSON plan that the
Python backend parses and executes locally. Works with any LLM.
"""

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
from app.core.tool_registry import execute_tool, get_tools

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
        yield _sse("error", {"message": "LLM Manager not initialized"})
        return

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
        yield _sse("error", {"message": str(exc)})
        return

    choice = response.choices[0]  # type: ignore[union-attr]
    msg = choice.message

    if getattr(msg, "reasoning_content", None):
        yield _sse("thinking", {"content": msg.reasoning_content})  # type: ignore[union-attr]

    full_text = msg.content or ""

    # Parse JSON action plan from the response
    actions = _parse_actions(full_text)

    if actions:
        # Remove the JSON block from visible text, leave just the summary
        visible_text = _strip_json_blocks(full_text).strip()
        if visible_text:
            yield _sse("token", {"content": visible_text})
            yield _sse("token", {"content": "\n\n"})

        # Execute each action locally
        for i, action in enumerate(actions):
            tool_name = action.get("tool", "")
            tool_args = action.get("args", {})

            yield _sse("tool_call", {
                "id": f"local_{i}",
                "name": tool_name,
                "args": tool_args,
            })

            t0 = asyncio.get_event_loop().time()
            result = await execute_tool(tool_name, tool_args, OBSIDIAN_VAULT_PATH)
            elapsed = round((asyncio.get_event_loop().time() - t0) * 1000)

            yield _sse("tool_result", {
                "id": f"local_{i}",
                "name": tool_name,
                "content": result,
                "elapsed_ms": elapsed,
            })

        yield _sse("token", {"content": f"\nDone — {len(actions)} action(s) completed."})
    else:
        # No JSON plan — just stream the text response as-is
        yield _sse("token", {"content": full_text})

    yield "data: [DONE]\n\n"


def _parse_actions(text: str) -> list[dict]:
    """Extract JSON action plan from LLM response."""
    # Try ```json ... ``` blocks
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
