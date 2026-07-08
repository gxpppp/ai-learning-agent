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
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_create_and_read_note(client: AsyncClient, vault_dir: str):
    resp = await client.post(
        "/api/notes/create",
        json={
            "vault_path": vault_dir,
            "folder": "test",
            "filename": "hello.md",
            "content": "# Hello World",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["path"] == "test/hello.md"

    resp = await client.post(
        "/api/notes/read",
        json={"vault_path": vault_dir, "path": "test/hello.md"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["content"] == "# Hello World"


@pytest.mark.asyncio
async def test_create_duplicate(client: AsyncClient, vault_dir: str):
    payload = {
        "vault_path": vault_dir,
        "folder": "test",
        "filename": "dup.md",
        "content": "first",
    }
    resp = await client.post("/api/notes/create", json=payload)
    assert resp.json()["success"] is True

    resp = await client.post("/api/notes/create", json=payload)
    assert resp.json()["success"] is False
    assert resp.json()["error"] == "File already exists"


@pytest.mark.asyncio
async def test_update_note(client: AsyncClient, vault_dir: str):
    await client.post(
        "/api/notes/create",
        json={
            "vault_path": vault_dir,
            "folder": "",
            "filename": "update-test.md",
            "content": "original",
        },
    )
    resp = await client.post(
        "/api/notes/update",
        json={
            "vault_path": vault_dir,
            "path": "update-test.md",
            "content": "updated",
        },
    )
    assert resp.json()["success"] is True

    resp = await client.post(
        "/api/notes/read",
        json={"vault_path": vault_dir, "path": "update-test.md"},
    )
    assert resp.json()["content"] == "updated"


@pytest.mark.asyncio
async def test_delete_note(client: AsyncClient, vault_dir: str):
    await client.post(
        "/api/notes/create",
        json={
            "vault_path": vault_dir,
            "folder": "",
            "filename": "delete-me.md",
            "content": "bye",
        },
    )
    resp = await client.post(
        "/api/notes/delete",
        json={"vault_path": vault_dir, "path": "delete-me.md"},
    )
    assert resp.json()["success"] is True

    resp = await client.post(
        "/api/notes/read",
        json={"vault_path": vault_dir, "path": "delete-me.md"},
    )
    assert resp.json()["success"] is False


@pytest.mark.asyncio
async def test_read_nonexistent(client: AsyncClient, vault_dir: str):
    resp = await client.post(
        "/api/notes/read",
        json={"vault_path": vault_dir, "path": "nope.md"},
    )
    assert resp.json()["success"] is False
    assert resp.json()["error"] == "File not found"


@pytest.mark.asyncio
async def test_path_traversal_blocked(client: AsyncClient, vault_dir: str):
    resp = await client.post(
        "/api/notes/read",
        json={"vault_path": vault_dir, "path": "../etc/passwd"},
    )
    assert resp.status_code == 403
