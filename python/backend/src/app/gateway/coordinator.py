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
        self._call_seq = 0
        self._tool_times: dict[str, float] = {}

    async def execute(
        self,
        user_message: str,
        system_prompt: str,
        provider_id: str,
        model: str,
        conversation: list[dict[str, Any]] | None = None,
    ) -> AsyncGenerator[str, None]:
        """Execute a task using OpenHarness QueryEngine.

        Uses OpenAICompatibleClient from openharness for proper
        tool_use → tool_result cycle handling.
        """
        import app.llm.manager as _llm_mgr
        from app.core.event_bus import done_event, error_event
        from app.gateway.tools_adapter import create_vault_tool_registry
        from openharness.api import OpenAICompatibleClient
        from openharness.engine.messages import ConversationMessage, TextBlock

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

        # Build tool registry with all vault tools
        tool_registry = create_vault_tool_registry()

        # Auto-approve all tool calls
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

        # Load conversation history if provided
        if conversation:
            history_msgs: list[ConversationMessage] = []
            for m in conversation:
                role = m.get("role", "user")
                content = m.get("content", "")
                if role == "user":
                    history_msgs.append(ConversationMessage.from_user_text(content))
                elif role == "assistant":
                    history_msgs.append(ConversationMessage(
                        role="assistant",
                        content=[TextBlock(text=content, type="text")],
                    ))
            engine.load_messages(history_msgs)

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
        import time

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
                self._call_seq += 1
                tid = f"{name}_{self._call_seq}"
                self._tool_times[tid] = time.time()
                return tool_call_event(tid, name, inp)

            case ToolExecutionCompleted(tool_name=name, output=out, is_error=_is_err):
                # Find the matching start time
                elapsed = 0
                for tid, t0 in list(self._tool_times.items()):
                    if tid.startswith(name + "_"):
                        elapsed = int((time.time() - t0) * 1000)
                        del self._tool_times[tid]
                        return tool_result_event(tid, name, out, elapsed)

                self._call_seq += 1
                tid = f"{name}_{self._call_seq}"
                return tool_result_event(tid, name, out, 0)

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
