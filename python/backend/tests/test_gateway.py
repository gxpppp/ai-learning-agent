"""Integration tests for the gateway layer — E2E task routing and agent dispatch."""

from __future__ import annotations

import json
import tempfile

import pytest
import pytest_asyncio

from app.core.dispatcher import TaskComplexity, classify


class TestDispatcher:
    """Test the intent classifier."""

    def test_simple_message(self):
        assert classify("Hello how are you") == TaskComplexity.SIMPLE

    def test_simple_tool_request(self):
        assert classify("read my note about Rust") == TaskComplexity.SIMPLE

    def test_search_chinese(self):
        assert classify("search Rust ownership") == TaskComplexity.SEARCH

    def test_search_knowledge(self):
        assert classify("what is deep learning") == TaskComplexity.SEARCH

    def test_search_find(self):
        assert classify("find notes about Python") == TaskComplexity.SEARCH

    def test_search_english(self):
        assert classify("search for notes about machine learning") == TaskComplexity.SEARCH

    def test_search_what_is(self):
        assert classify("什么是深度学习") == TaskComplexity.SEARCH

    def test_complex_organize(self):
        assert classify("帮我整理一下Rust目录的笔记") == TaskComplexity.COMPLEX

    def test_complex_batch(self):
        assert classify("给所有笔记打上合适的标签") == TaskComplexity.COMPLEX

    def test_complex_english(self):
        assert classify("organize all my notes in the Projects folder") == TaskComplexity.COMPLEX


class TestMemory:
    """Test persistent memory operations."""

    def test_save_and_load(self):
        from app.gateway.memory import load_memory, save_memory
        with tempfile.TemporaryDirectory() as tmpdir:
            save_memory(tmpdir, "test_key", {"hello": "world"})
            result = load_memory(tmpdir, "test_key")
            assert result == {"hello": "world"}

    def test_load_default(self):
        from app.gateway.memory import load_memory
        result = load_memory("/nonexistent/vault", "no_such_key", {"default": True})
        assert result == {"default": True}

    def test_user_profile_roundtrip(self):
        from app.gateway.memory import load_user_profile, save_user_profile
        with tempfile.TemporaryDirectory() as tmpdir:
            profile = {"name": "Test", "preferences": {"tone": "concise"}}
            save_user_profile(tmpdir, profile)
            loaded = load_user_profile(tmpdir)
            assert loaded["name"] == "Test"
            assert loaded["preferences"]["tone"] == "concise"

    def test_add_recent_topic(self):
        from app.gateway.memory import add_recent_topic, load_user_profile
        with tempfile.TemporaryDirectory() as tmpdir:
            add_recent_topic(tmpdir, "Rust")
            add_recent_topic(tmpdir, "Python")
            add_recent_topic(tmpdir, "Rust")  # should move to top
            profile = load_user_profile(tmpdir)
            assert profile["recent_topics"][0] == "Rust"
            assert profile["recent_topics"][1] == "Python"


class TestSession:
    """Test session persistence."""

    def test_create_and_load_session(self):
        from app.gateway.session import create_session, load_session, save_message
        with tempfile.TemporaryDirectory() as tmpdir:
            record = create_session(tmpdir, {"topic": "testing"})
            save_message(tmpdir, record.session_id, {"role": "user", "content": "hello"})
            save_message(tmpdir, record.session_id, {"role": "assistant", "content": "hi"})

            loaded = load_session(tmpdir, record.session_id)
            assert loaded is not None
            assert len(loaded.messages) == 2
            assert loaded.messages[0]["role"] == "user"
            assert loaded.metadata["topic"] == "testing"

    def test_list_sessions(self):
        from app.gateway.session import create_session, list_sessions
        import time
        with tempfile.TemporaryDirectory() as tmpdir:
            create_session(tmpdir, {"id": "s1"})
            time.sleep(1)
            create_session(tmpdir, {"id": "s2"})
            sessions = list_sessions(tmpdir)
            assert len(sessions) == 2

    def test_load_nonexistent_session(self):
        from app.gateway.session import load_session
        result = load_session("/nonexistent/vault", "no_such_session")
        assert result is None


class TestVaultOps:
    """Test core vault operations."""

    def test_safe_path_normal(self):
        from app.core.vault_ops import safe_path
        path = safe_path("/vault", "notes/test.md")
        assert path.endswith("notes\\test.md") or path.endswith("notes/test.md")

    def test_safe_path_traversal(self):
        from app.core.vault_ops import safe_path
        with pytest.raises(ValueError):
            safe_path("/vault", "../etc/passwd")

    def test_read_write_note(self):
        from app.core.vault_ops import read_note, write_note
        with tempfile.TemporaryDirectory() as tmpdir:
            write_note(tmpdir, "test.md", "# Hello\nWorld")
            content = read_note(tmpdir, "test.md")
            assert "# Hello" in content

    def test_list_folder(self):
        from app.core.vault_ops import create_folder, list_folder, write_note
        with tempfile.TemporaryDirectory() as tmpdir:
            create_folder(tmpdir, "subdir")
            write_note(tmpdir, "subdir/one.md", "one")
            items = list_folder(tmpdir, "subdir")
            assert len(items) == 1
            assert items[0]["name"] == "one.md"

    def test_delete_note(self):
        from app.core.vault_ops import delete_note, write_note
        import os
        with tempfile.TemporaryDirectory() as tmpdir:
            write_note(tmpdir, "to_delete.md", "bye")
            result = delete_note(tmpdir, "to_delete.md")
            assert ".trash/" in result
            assert os.path.exists(os.path.join(tmpdir, ".trash", "to_delete.md"))

    def test_move_note(self):
        from app.core.vault_ops import move_note, read_note, write_note
        with tempfile.TemporaryDirectory() as tmpdir:
            write_note(tmpdir, "src/move_me.md", "moving")
            move_note(tmpdir, "src/move_me.md", "dst/moved.md")
            content = read_note(tmpdir, "dst/moved.md")
            assert "moving" in content


class TestGraph:
    """Test knowledge graph generation."""

    def test_empty_vault(self):
        from app.infra.graph import generate_graph
        with tempfile.TemporaryDirectory() as tmpdir:
            result = generate_graph(tmpdir)
            assert result["nodes"] == []
            assert result["links"] == []
            assert result["total_notes"] == 0

    def test_single_note(self):
        from app.infra.graph import generate_graph
        with tempfile.TemporaryDirectory() as tmpdir:
            note_path = tmpdir + "/test.md"
            with open(note_path, "w", encoding="utf-8") as f:
                f.write("---\ntags:\n  - rust\n---\n\n# Test Note\n\nHello world.")
            result = generate_graph(tmpdir)
            assert len(result["nodes"]) == 1
            assert result["nodes"][0]["name"] == "test"
            assert "rust" in result["nodes"][0]["tags"]

    def test_linked_notes(self):
        from app.infra.graph import generate_graph
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(tmpdir + "/a.md", "w", encoding="utf-8") as f:
                f.write("# Note A\n\nSee [[b]] for more.")
            with open(tmpdir + "/b.md", "w", encoding="utf-8") as f:
                f.write("# Note B\n\nThis is referenced by [[a]].")
            result = generate_graph(tmpdir)
            assert len(result["nodes"]) == 2
            assert len(result["links"]) >= 1
