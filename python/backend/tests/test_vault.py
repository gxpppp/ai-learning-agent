"""Tests for vault indexing endpoints."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_vault_index_no_path(client: AsyncClient):
    resp = await client.post("/api/vault/index", json={})
    assert resp.status_code in (400, 422, 503)


@pytest.mark.asyncio
async def test_vault_status_no_vault(client: AsyncClient):
    resp = await client.get("/api/vault/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "no_vault"
