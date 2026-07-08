"""Tests for tags and links endpoints."""

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
async def test_tags_suggest_uninitialized(client: AsyncClient):
    resp = await client.post("/api/tags/suggest", json={"note_path": "test.md"})
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_links_recommend_uninitialized(client: AsyncClient):
    resp = await client.post("/api/links/recommend", json={"note_path": "test.md"})
    assert resp.status_code == 503
