"""Gateway task router — classify intent and dispatch to agents or direct tools."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator

from app.core.dispatcher import TaskComplexity, classify
from app.core.tool_registry import execute_tool

logger = logging.getLogger(__name__)


async def route(
    user_message: str,
    vault_path: str,
    conversation: list[dict] | None = None,
) -> AsyncGenerator[str, None]:
    """Route a user message to the appropriate handler.

    Yields SSE event strings.
    """
    from app.core.event_bus import agent_end_event, agent_start_event, token_event

    complexity = classify(user_message)

    if complexity == TaskComplexity.SIMPLE:
        # Simple single-step: no special orchestration needed
        # Let the current agent.py handle with JSON plan parsing
        return  # Signal: let caller use existing simple path

    elif complexity == TaskComplexity.SEARCH:
        yield agent_start_event("searcher", user_message[:80])
        async for event in _handle_search(user_message, vault_path, conversation):
            yield event
        yield agent_end_event("searcher", "done")

    elif complexity == TaskComplexity.COMPLEX:
        yield agent_start_event("orchestrator", user_message[:80])
        yield token_event("This is a complex task. Multi-agent orchestration will be available in Stage 3.\n\n")
        yield token_event("For now, I'll handle this step by step:\n\n")
        # Fallback: treat as simple for now
        yield agent_end_event("orchestrator", "fallback-to-simple")


async def _handle_search(
    query: str,
    vault_path: str,
    conversation: list[dict] | None = None,
) -> AsyncGenerator[str, None]:
    """Handle search-intent queries: local RAG + web search."""
    from app.core.dispatcher import should_use_local_rag, should_use_web_search
    from app.core.event_bus import (
        error_event,
        token_event,
        tool_call_event,
        tool_result_event,
    )

    # 1. Local RAG search
    if should_use_local_rag(query):
        yield token_event("Searching your vault...\n\n")
        t0 = asyncio.get_event_loop().time()
        yield tool_call_event("search_0", "search_notes", {"query": query})
        try:
            result = await execute_tool("search_notes", {"query": query}, vault_path)
            elapsed = round((asyncio.get_event_loop().time() - t0) * 1000)
            yield tool_result_event("search_0", "search_notes", result, elapsed)
        except Exception as e:
            yield error_event(f"Vault search failed: {e}")

    # 2. Web search
    if should_use_web_search(query):
        yield token_event("Searching the web...\n\n")
        t0 = asyncio.get_event_loop().time()
        yield tool_call_event("web_0", "web_search", {"query": query})
        try:
            from app.llm.search import search_web

            results = await search_web(query)
            formatted = "\n".join(
                f"- [{r.title}]({r.url}): {r.content[:200]}" for r in results
            ) if results else "No web results found."
            elapsed = round((asyncio.get_event_loop().time() - t0) * 1000)
            yield tool_result_event("web_0", "web_search", formatted, elapsed)
        except Exception as e:
            yield error_event(f"Web search failed: {e}")

    # 3. If neither RAG nor web, just acknowledge
    if not should_use_local_rag(query) and not should_use_web_search(query):
        yield token_event("I can help you search your vault or the web. Try asking about your notes or a topic.\n")
