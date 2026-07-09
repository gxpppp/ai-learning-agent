"""OpenHarness Coordinator wrapper — embeds QueryEngine for multi-agent chat."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from openharness.config.settings import PermissionSettings
from openharness.engine import QueryEngine
from openharness.engine.stream_events import (
    AssistantTextDelta,
    AssistantTurnComplete,
    ErrorEvent,
    StreamEvent,
    ToolExecutionCompleted,
    ToolExecutionStarted,
)
from openharness.permissions import PermissionMode
from openharness.permissions.checker import PermissionChecker

logger = logging.getLogger(__name__)


class GatewayCoordinator:
    """High-level coordinator that wraps OpenHarness QueryEngine for Obsidian tasks."""

    def __init__(self, vault_path: str, permission_mode: str = "readonly"):
        self.vault_path = vault_path
        self.permission_mode = permission_mode

    async def execute(
        self,
        user_message: str,
        system_prompt: str,
        provider_id: str,
        model: str,
    ) -> AsyncGenerator[str, None]:
        """Execute a task using OpenHarness QueryEngine.

        Uses OpenAICompatibleClient from openharness for proper
        tool_use → tool_result cycle handling.
        """
        import app.llm.manager as _llm_mgr
        from app.core.event_bus import done_event, error_event
        from app.gateway.tools_adapter import create_vault_tool_registry
        from openharness.api import OpenAICompatibleClient

        if not _llm_mgr.llm_manager:
            yield error_event("LLM Manager not initialized")
            return

        provider = _llm_mgr.llm_manager.get_provider(provider_id)
        if not provider:
            yield error_event(f"Provider not found: {provider_id}")
            return

        # Use openharness's own OpenAI client for proper tool-call parsing
        api_client = OpenAICompatibleClient(
            api_key=provider.get("apiKey", ""),
            base_url=provider.get("baseUrl", "https://api.deepseek.com/v1"),
        )

        # Build tool registry with all 15 vault tools
        tool_registry = create_vault_tool_registry()

        # Auto-approve all tool calls (permissions managed at caller level)
        perm_settings = PermissionSettings(mode=PermissionMode.FULL_AUTO)
        perm_checker = PermissionChecker(perm_settings)

        # Build engine
        engine = QueryEngine(
            api_client=api_client,
            tool_registry=tool_registry,
            permission_checker=perm_checker,
            cwd=Path(self.vault_path),
            model=model,
            system_prompt=system_prompt,
            max_turns=8,
        )

        # Run the agent loop and stream results as SSE
        try:
            async for event in engine.submit_message(user_message):
                sse = self._map_event(event)
                if sse:
                    yield sse
        except Exception as exc:
            logger.exception("Agent loop failed")
            yield error_event(str(exc))

        yield done_event()

    def _map_event(self, event: StreamEvent) -> str | None:
        """Map OpenHarness StreamEvent to our SSE event string."""
        from app.core.event_bus import (
            error_event,
            token_event,
            tool_call_event,
            tool_result_event,
        )

        match event:
            case AssistantTextDelta(text=text):
                return token_event(text)

            case ToolExecutionStarted(tool_name=name, tool_input=inp):
                return tool_call_event(name, name, inp)

            case ToolExecutionCompleted(tool_name=name, output=out, is_error=_):
                return tool_result_event(name, name, out, 0)

            case ErrorEvent(message=msg):
                return error_event(msg)

            case AssistantTurnComplete():
                return None

            case _:
                return None


# Module singleton
coordinator: GatewayCoordinator | None = None


def get_coordinator(vault_path: str, permission_mode: str = "readonly") -> GatewayCoordinator:
    """Get or create the gateway coordinator."""
    global coordinator
    if coordinator is None:
        coordinator = GatewayCoordinator(vault_path, permission_mode)
    return coordinator
