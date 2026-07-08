"""Tests for word cloud endpoint."""

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
async def test_wordcloud_generate_uninitialized(client: AsyncClient):
    resp = await client.post("/api/wordcloud/generate", json={})
    assert resp.status_code == 503
