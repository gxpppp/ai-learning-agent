"""Tests for OCR endpoints."""

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
async def test_ocr_disabled_by_default(client: AsyncClient):
    resp = await client.get("/api/ocr/health")
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_ocr_parse_disabled_by_default(client: AsyncClient):
    resp = await client.post("/api/ocr/parse", json={"file_path": "/tmp/test.png"})
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_ocr_parse_and_save_disabled_by_default(client: AsyncClient):
    resp = await client.post(
        "/api/ocr/parse-and-save",
        json={
            "file_path": "/tmp/test.png",
            "vault_path": "/tmp/vault",
        },
    )
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_ocr_parse_invalid_task(client: AsyncClient, monkeypatch):
    monkeypatch.setenv("OCR_ENABLED", "true")
    from app import config
    monkeypatch.setattr(config, "OCR_ENABLED", True)
    # Need to reload the router... actually this won't work easily in-memory.
    # Just test validation on the request model.
    import pydantic

    from app.models.ocr import OcrParseRequest

    with pytest.raises(pydantic.ValidationError):
        OcrParseRequest(file_path="/tmp/test.png", task="invalid")  # type: ignore[arg-type]
