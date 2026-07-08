import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_chat_stream_requires_messages(client: AsyncClient):
    resp = await client.post("/api/chat/stream", json={})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_chat_stream_empty_messages(client: AsyncClient):
    resp = await client.post("/api/chat/stream", json={"messages": []})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "text/event-stream; charset=utf-8"


@pytest.mark.asyncio
async def test_chat_stream_invalid_json(client: AsyncClient):
    resp = await client.post(
        "/api/chat/stream",
        content=b"not json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 422
