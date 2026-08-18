"""tests/test_server_endpoints.py — HTTP contract tests for transcription endpoints."""
import pytest
from httpx import ASGITransport, AsyncClient

from app.server import app
from app.database import initialize_db


@pytest.fixture(autouse=True)
def setup_db():
    initialize_db()
    yield


@pytest.mark.asyncio
async def test_status_endpoint_returns_404_for_unknown_session():
    """GET /transcribe/status/{id} returns 404 for unknown job."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/transcribe/status/nonexistent-id")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_cancel_unknown_session_is_404():
    """DELETE /transcribe/{id} returns 404 — audio-less unknown ids are not created."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.delete("/transcribe/cancel-id")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_transcribe_requires_json_paths():
    """POST /transcribe rejects uploads without audio_paths."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/transcribe", json={})
        assert response.status_code == 422
