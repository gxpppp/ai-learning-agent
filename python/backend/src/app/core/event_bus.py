"""Unified SSE event bus — single place for all streaming event emission."""

from __future__ import annotations

import json


def format_sse(event: str, data: dict | str) -> str:
    """Format an SSE frame: event: <type>\ndata: <json>\n\n"""
    payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


def token_event(content: str) -> str:
    """SSE event for a streaming text token."""
    return format_sse("token", {"content": content})


def thinking_event(content: str) -> str:
    """SSE event for reasoning/thinking content (collapsible block)."""
    return format_sse("thinking", {"content": content})


def tool_call_event(tool_id: str, name: str, args: dict) -> str:
    """SSE event when a tool is about to be called."""
    return format_sse("tool_call", {"id": tool_id, "name": name, "args": args})


def tool_result_event(tool_id: str, name: str, content: str, elapsed_ms: int) -> str:
    """SSE event with a tool execution result."""
    return format_sse("tool_result", {
        "id": tool_id,
        "name": name,
        "content": content,
        "elapsed_ms": elapsed_ms,
    })


def agent_start_event(agent_name: str, task: str) -> str:
    """SSE event when a sub-agent starts work."""
    return format_sse("agent_start", {"agent": agent_name, "task": task})


def agent_end_event(agent_name: str, status: str) -> str:
    """SSE event when a sub-agent finishes."""
    return format_sse("agent_end", {"agent": agent_name, "status": status})


def error_event(message: str) -> str:
    """SSE event for errors."""
    return format_sse("error", {"message": message})


def done_event() -> str:
    """SSE stream termination."""
    return "data: [DONE]\n\n"


def heartbeat() -> str:
    """SSE heartbeat to keep connection alive."""
    return ": heartbeat\n\n"
