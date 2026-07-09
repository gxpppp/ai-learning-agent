"""Tests for tool registry — exercise tool execution and path safety."""

import json
import os
import tempfile

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def vault_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_tool_path_traversal_blocked(vault_dir: str):
    """Tool execution should block path traversal."""
    from app.core.tool_registry import _safe_path
    with pytest.raises(ValueError):
        _safe_path(vault_dir, "../etc/passwd")


@pytest.mark.asyncio
async def test_tool_list_folder_empty(vault_dir: str):
    from app.core.tool_registry import _list_folder
    result = _list_folder({"path": ""}, vault_dir)
    data = json.loads(result)
    assert data["count"] == 0


@pytest.mark.asyncio
async def test_tool_create_folder(vault_dir: str):
    from app.core.tool_registry import _create_folder
    result = _create_folder({"path": "test-subdir"}, vault_dir)
    data = json.loads(result)
    assert data["created_folder"] == "test-subdir"
    assert os.path.isdir(os.path.join(vault_dir, "test-subdir"))


@pytest.mark.asyncio
async def test_tool_create_and_read_note(vault_dir: str):
    from app.core.tool_registry import _create_note, _read_note
    _create_note({
        "folder": "",
        "filename": "test.md",
        "content": "# Hello\nWorld",
        "tags": ["test"],
    }, vault_dir)
    result = _read_note({"note_path": "test.md"}, vault_dir)
    data = json.loads(result)
    assert "# Hello" in data["content"]


@pytest.mark.asyncio
async def test_tool_delete_note(vault_dir: str):
    from app.core.tool_registry import _create_note, _delete_note
    _create_note({
        "folder": "",
        "filename": "to-delete.md",
        "content": "bye",
    }, vault_dir)
    _delete_note({"note_path": "to-delete.md"}, vault_dir)
    assert not os.path.exists(os.path.join(vault_dir, "to-delete.md"))
    # Moved to .trash
    assert os.path.exists(os.path.join(vault_dir, ".trash", "to-delete.md"))


@pytest.mark.asyncio
async def test_tool_move_note(vault_dir: str):
    from app.core.tool_registry import _create_note, _move_note, _read_note
    _create_note({
        "folder": "src",
        "filename": "move-me.md",
        "content": "move",
    }, vault_dir)
    _move_note({"source": "src/move-me.md", "destination": "dst/moved.md"}, vault_dir)
    result = _read_note({"note_path": "dst/moved.md"}, vault_dir)
    assert "move" in json.loads(result)["content"]


@pytest.mark.asyncio
async def test_tool_unknown(vault_dir: str):
    from app.core.tool_registry import execute_tool
    result = await execute_tool("nonexistent", {}, vault_dir)
    data = json.loads(result)
    assert "Unknown tool" in data["error"]


@pytest.mark.asyncio
async def test_tool_file_not_found(vault_dir: str):
    from app.core.tool_registry import _read_note
    result = _read_note({"note_path": "nope.md"}, vault_dir)
    data = json.loads(result)
    assert "File not found" in data["error"]
