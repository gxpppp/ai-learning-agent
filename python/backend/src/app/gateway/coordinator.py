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
from openharness.permissions.checker import PermissionChecker
from openharness.permissions.types import PermissionMode

logger = logging.getLogger(__name__)


class OpenAIBridgeClient:
    """Bridge our llm/client.py to the OpenHarness streaming API protocol."""

    def __init__(self, llm_manager, provider_id: str, model: str):
        self._llm_manager = llm_manager
        self._provider_id = provider_id
        self._model = model

    async def stream_message(self, request: Any) -> AsyncGenerator[Any, None]:
        """Stream a chat completion using our existing LLM client."""
        import json

        from openharness.api.types import (
            ApiMessageCompleteEvent,
            ApiTextDeltaEvent,
        )

        # Convert OpenHarness messages to the format our llm_manager expects
        client = self._llm_manager.get_chat_client(self._provider_id, self._model)

        messages = []
        for msg in request.messages:
            messages.append({
                "role": msg.role,
                "content": msg.text if hasattr(msg, "text") else "",
            })

        # Call our existing LLM client
        try:
            response = await client.async_client.chat.completions.create(
                model=self._model,
                messages=messages,
                tools=request.tools if hasattr(request, "tools") else None,
                temperature=0.7,
                stream=True,
            )

            async for chunk in response:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    yield ApiTextDeltaEvent(text=delta.content)

                # Handle tool calls if present
                if delta and getattr(delta, "tool_calls", None):
                    for tc in delta.tool_calls:
                        if tc.function:
                            yield ApiTextDeltaEvent(
                                text=json.dumps({
                                    "tool_call": {
                                        "id": tc.id or "",
                                        "name": tc.function.name or "",
                                        "arguments": tc.function.arguments or "{}",
                                    }
                                })
                            )

            yield ApiMessageCompleteEvent(usage={"total_tokens": 0})

        except Exception:
            logger.exception("LLM bridge stream failed")
            yield ApiMessageCompleteEvent(usage={"total_tokens": 0})


class GatewayCoordinator:
    """High-level coordinator that wraps OpenHarness QueryEngine for Obsidian tasks."""

    def __init__(
        self,
        vault_path: str,
        permission_mode: str = "readonly",
    ):
        self.vault_path = vault_path
        self.permission_mode = permission_mode

    async def execute_simple(
        self,
        user_message: str,
        system_prompt: str,
        provider_id: str,
        model: str,
    ) -> AsyncGenerator[str, None]:
        """Execute a simple task using QueryEngine directly.

        Yields SSE event strings.
        """
        import app.llm.manager as _llm_mgr
        from app.core.event_bus import (
            done_event,
            error_event,
        )
        from app.gateway.tools_adapter import create_vault_tool_registry

        if not _llm_mgr.llm_manager:
            yield error_event("LLM Manager not initialized")
            return

        # Build tool registry
        tool_registry = create_vault_tool_registry()

        # Build API client bridge
        api_client = OpenAIBridgeClient(_llm_mgr.llm_manager, provider_id, model)

        # Build permission checker (auto-approve for vault tools)
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

        # Submit and stream events
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
                return tool_call_event(name, name, inp)  # name as id

            case ToolExecutionCompleted(tool_name=name, output=out, is_error=_is_err):
                return tool_result_event(name, name, out, 0)

            case ErrorEvent(message=msg):
                return error_event(msg)

            case AssistantTurnComplete():
                return None  # Handled by done_event

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
