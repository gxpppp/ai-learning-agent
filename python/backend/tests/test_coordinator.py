"""E2E tests for GatewayCoordinator with mock LLM."""

from __future__ import annotations

import asyncio
import json
import tempfile
from typing import Any

import pytest
import pytest_asyncio


# ─── Mock streaming LLM client ───


class MockDeltaEvent:
    """Simulates an AssistantTextDelta."""

    def __init__(self, text: str):
        self.text = text


class MockCompleteEvent:
    """Simulates an AssistantTurnComplete."""

    def __init__(self):
        self.usage = type("Usage", (), {"total_tokens": 100})


class MockStreamResponse:
    """Simulates an OpenAI streaming response."""

    def __init__(self, responses: list[str]):
        self._responses = responses
        self._idx = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._idx >= len(self._responses):
            raise StopAsyncIteration
        text = self._responses[self._idx]
        self._idx += 1

        class Choice:
            class Delta:
                content = text
            delta = Delta()

        class Chunk:
            choices = [Choice()]

        return Chunk()


class MockLLMClient:
    """Mock LLM client that returns predetermined responses."""

    def __init__(self, response_text: str):
        self._response_text = response_text
        self.call_count = 0

    async def stream_message(self, request: Any) -> Any:
        self.call_count += 1
        yield type("MockDelta", (), {"text": self._response_text})()
        yield type("MockComplete", (), {"usage": None})()


class MockChatClient:
    """Mock async chat client for the agent.py path."""

    def __init__(self, response_text: str, has_json_plan: bool = True):
        self._response_text = response_text
        self._has_json_plan = has_json_plan

    @property
    def async_client(self):
        return self

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    async def create(self, **kwargs: Any) -> Any:
        content = self._response_text
        if self._has_json_plan:
            plan = json.dumps({
                "actions": [
                    {"tool": "read_note", "args": {"note_path": "test.md"}}
                ],
                "summary": "Reading the test note",
            })
            content = f"Let me help you.\n```json\n{plan}\n```"

        class Message:
            content = content
            reasoning_content = None

        class Choice:
            message = Message()

        return type("Response", (), {"choices": [Choice()]})()


# ─── Fixtures ───


@pytest.fixture
def vault_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(f"{tmpdir}/test.md", "w", encoding="utf-8") as f:
            f.write("# Hello World\nThis is a test note.")
        yield tmpdir


# ─── Tests ───


class TestCoordinatorMock:
    """Test GatewayCoordinator with a mock LLM."""

    @pytest.mark.asyncio
    async def test_coordinator_simple_response(self, vault_dir: str):
        """Coordinator handles a simple text response without tool calls."""
        from app.config import ACTIVE_CHAT_MODEL, ACTIVE_PROVIDER_ID

        # We can't easily mock the llm_manager singleton, so test the event
        # mapping logic directly instead
        from app.gateway.coordinator import GatewayCoordinator

        coordinator = GatewayCoordinator(vault_path=vault_dir)

        # Test _map_event directly
        from openharness.engine.stream_events import AssistantTextDelta, ToolExecutionStarted, ToolExecutionCompleted

        ev1 = coordinator._map_event(AssistantTextDelta(text="Hello"))
        assert ev1 is not None
        assert "token" in ev1

        ev2 = coordinator._map_event(
            ToolExecutionStarted(tool_name="read_note", tool_input={"note_path": "x.md"})
        )
        assert ev2 is not None
        assert "tool_call" in ev2

        ev3 = coordinator._map_event(
            ToolExecutionCompleted(tool_name="read_note", output="content", is_error=False)
        )
        assert ev3 is not None
        assert "tool_result" in ev3

        # None for completion (handled by caller)
        from openharness.engine.stream_events import AssistantTurnComplete
        from openharness.engine.messages import ConversationMessage
        ev4 = coordinator._map_event(AssistantTurnComplete(
            message=ConversationMessage(role="assistant", content=[]),
            usage=None,
        ))
        assert ev4 is None

    @pytest.mark.asyncio
    async def test_coordinator_with_tools(self, vault_dir: str):
        """Coordinator event mapping preserves tool call data."""
        import json

        from app.gateway.coordinator import GatewayCoordinator
        from openharness.engine.stream_events import ToolExecutionCompleted, ToolExecutionStarted

        coordinator = GatewayCoordinator(vault_path=vault_dir)

        # Start a tool
        start_event = coordinator._map_event(
            ToolExecutionStarted(tool_name="search_notes", tool_input={"query": "rust"})
        )
        assert "search_notes" in start_event
        assert "rust" in start_event

        # Complete a tool with JSON result
        result = json.dumps({"results": [{"path": "rust/basics.md", "score": 0.9}]})
        end_event = coordinator._map_event(
            ToolExecutionCompleted(tool_name="search_notes", output=result, is_error=False)
        )
        assert "tool_result" in end_event
        assert "search_notes" in end_event


class TestDispatcherEnhanced:
    """Enhanced dispatcher tests."""

    def test_create_note_simple(self):
        from app.core.dispatcher import TaskComplexity, classify
        assert classify("create a note about Python") == TaskComplexity.SIMPLE

    def test_read_note_simple(self):
        from app.core.dispatcher import TaskComplexity, classify
        assert classify("read Rust/basics.md") == TaskComplexity.SIMPLE

    def test_list_notes_simple(self):
        from app.core.dispatcher import TaskComplexity, classify
        assert classify("list my root folder") == TaskComplexity.SIMPLE

    def test_greeting_simple(self):
        from app.core.dispatcher import TaskComplexity, classify
        assert classify("hello") == TaskComplexity.SIMPLE


class TestEventBus:
    """Test SSE event formatting."""

    def test_token_event(self):
        from app.core.event_bus import token_event
        result = token_event("hello world")
        assert "event: token" in result
        assert "hello world" in result
        assert result.endswith("\n\n")

    def test_tool_call_event(self):
        from app.core.event_bus import tool_call_event
        result = tool_call_event("t1", "search_notes", {"query": "x"})
        assert "event: tool_call" in result
        assert "search_notes" in result
        assert result.endswith("\n\n")

    def test_tool_result_event(self):
        from app.core.event_bus import tool_result_event
        result = tool_result_event("t1", "search_notes", "results here", 42)
        assert "event: tool_result" in result
        assert "42" in result
        assert "results here" in result
        assert result.endswith("\n\n")

    def test_error_event(self):
        from app.core.event_bus import error_event
        result = error_event("something went wrong")
        assert "event: error" in result
        assert "something went wrong" in result
        assert result.endswith("\n\n")

    def test_agent_start_event(self):
        from app.core.event_bus import agent_start_event
        result = agent_start_event("searcher", "find rust notes")
        assert "event: agent_start" in result
        assert "searcher" in result
        assert result.endswith("\n\n")

    def test_agent_end_event(self):
        from app.core.event_bus import agent_end_event
        result = agent_end_event("searcher", "done")
        assert "event: agent_end" in result
        assert "searcher" in result
        assert result.endswith("\n\n")

    def test_heartbeat(self):
        from app.core.event_bus import heartbeat
        result = heartbeat()
        assert result == ": heartbeat\n\n"

    def test_done_event(self):
        from app.core.event_bus import done_event
        result = done_event()
        assert result == "data: [DONE]\n\n"


class TestSearch:
    """Test search service (no real API)."""

    def test_search_disabled_by_default(self):
        from app.config import WEB_SEARCH_ENABLED
        assert not WEB_SEARCH_ENABLED


class TestExporter:
    """Test document exporter."""

    def test_export_empty_vault(self):
        from app.infra.exporter import export_to_markdown
        with tempfile.TemporaryDirectory() as src_dir:
            with tempfile.TemporaryDirectory() as out_dir:
                result = export_to_markdown(src_dir, out_dir)
                assert result["exported"] == 0

    def test_export_single_note(self):
        from app.infra.exporter import export_to_markdown
        import os
        with tempfile.TemporaryDirectory() as src_dir:
            with open(f"{src_dir}/hello.md", "w", encoding="utf-8") as f:
                f.write("# Hello\nWorld")
            with tempfile.TemporaryDirectory() as out_dir:
                result = export_to_markdown(src_dir, out_dir)
                assert result["exported"] == 1
                assert os.path.exists(f"{out_dir}/hello.md")
                assert os.path.exists(f"{out_dir}/index.md")

    def test_wiki_link_conversion(self):
        from app.infra.exporter import _convert_wiki_links
        content = "See [[other]] for more."
        result = _convert_wiki_links(content, "/vault", "/vault/notes")
        assert "[other]" in result
        assert ".md" in result

    def test_frontmatter_tag_extraction(self):
        from app.infra.exporter import _extract_frontmatter_tags
        content = """---
tags:
  - rust
  - python
---
# Hello"""
        tags = _extract_frontmatter_tags(content)
        assert "rust" in tags
        assert "python" in tags


class TestEvolutionBridge:
    """Test evolution bridge."""

    def test_no_evolution_data(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from app.gateway.evolution_bridge import get_active_prompt
            prompt = get_active_prompt(tmpdir)
            assert prompt is None

    def test_inject_with_no_data(self):
        from app.gateway.evolution_bridge import inject_evolved_prompt
        with tempfile.TemporaryDirectory() as tmpdir:
            result = inject_evolved_prompt("Base prompt", tmpdir)
            assert result == "Base prompt"

    def test_active_prompt_loading(self):
        import os
        with tempfile.TemporaryDirectory() as tmpdir:
            evo_dir = os.path.join(tmpdir, ".ai-tutor", "evolution", "VARIANTS")
            os.makedirs(evo_dir, exist_ok=True)
            with open(os.path.join(evo_dir, "active.md"), "w", encoding="utf-8") as f:
                f.write("Be more concise. Use fewer words.")

            from app.gateway.evolution_bridge import get_active_prompt, inject_evolved_prompt

            prompt = get_active_prompt(tmpdir)
            assert "concise" in prompt

            result = inject_evolved_prompt("Base prompt", tmpdir)
            assert "Base prompt" in result
            assert "concise" in result


class TestGatewayCoordinator:
    """Test GatewayCoordinator initialization and event mapping."""

    def test_coordinator_init(self):
        from app.gateway.coordinator import GatewayCoordinator

        c = GatewayCoordinator("/tmp/test-vault", "readonly")
        assert c.vault_path == "/tmp/test-vault"
        assert c.permission_mode == "readonly"

    def test_map_text_event(self):
        from app.gateway.coordinator import GatewayCoordinator
        from openharness.engine.stream_events import AssistantTextDelta

        c = GatewayCoordinator("/tmp/vault")
        result = c._map_event(AssistantTextDelta(text="Hello world"))
        assert result is not None
        assert "event: token" in result
        assert "Hello world" in result

    def test_map_tool_start_event(self):
        from app.gateway.coordinator import GatewayCoordinator
        from openharness.engine.stream_events import ToolExecutionStarted

        c = GatewayCoordinator("/tmp/vault")
        result = c._map_event(ToolExecutionStarted(
            tool_name="search_notes",
            tool_input={"query": "rust"},
        ))
        assert result is not None
        assert "event: tool_call" in result
        assert "search_notes" in result

    def test_map_tool_complete_event(self):
        from app.gateway.coordinator import GatewayCoordinator
        from openharness.engine.stream_events import ToolExecutionCompleted

        c = GatewayCoordinator("/tmp/vault")
        result = c._map_event(ToolExecutionCompleted(
            tool_name="read_note",
            output='{"path": "test.md", "content": "hello"}',
            is_error=False,
        ))
        assert result is not None
        assert "event: tool_result" in result
        assert "read_note" in result

    def test_map_error_event(self):
        from app.gateway.coordinator import GatewayCoordinator
        from openharness.engine.stream_events import ErrorEvent

        c = GatewayCoordinator("/tmp/vault")
        result = c._map_event(ErrorEvent(message="Something broke", recoverable=False))
        assert result is not None
        assert "event: error" in result
        assert "Something broke" in result

    def test_map_unknown_event_returns_none(self):
        from app.gateway.coordinator import GatewayCoordinator
        from openharness.engine.stream_events import StatusEvent

        c = GatewayCoordinator("/tmp/vault")
        result = c._map_event(StatusEvent(message="status update"))
        assert result is None

    def test_get_coordinator_singleton(self):
        from app.gateway.coordinator import GatewayCoordinator, coordinator, get_coordinator

        # Reset singleton for test
        import app.gateway.coordinator as gc_mod
        gc_mod.coordinator = None

        c1 = get_coordinator("/vault1", "readonly")
        assert isinstance(c1, GatewayCoordinator)
        assert c1.vault_path == "/vault1"

        # Second call returns same instance
        c2 = get_coordinator("/vault2", "full")
        assert c2 is c1
        assert c2.vault_path == "/vault1"  # not updated
