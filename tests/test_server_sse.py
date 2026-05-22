"""tests/test_server_sse.py — Smoke tests for the FastAPI SSE transcription endpoint."""
import io
import struct
import wave
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.server import app
from app.database import initialize_db


@pytest.fixture(autouse=True)
def setup_db():
    initialize_db()
    yield


def make_silent_wav() -> io.BytesIO:
    """Create a minimal 1-second silent WAV (44.1kHz, 16-bit mono)."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(struct.pack("<h", 0) * 44100)
    buf.seek(0)
    return buf


@pytest.mark.asyncio
async def test_transcribe_endpoint_returns_sse_media_type():
    """POST /transcribe must return a StreamingResponse with text/event-stream."""
    # Mock the transcriber to avoid slow/real transcription
    async def mock_transcribe_events(*args, **kwargs):
        from app.server import _sse_frame
        yield _sse_frame("chunk", "test chunk")
        yield _sse_frame("chunk", "[DONE]")

    with patch("app.server._transcription_events", mock_transcribe_events):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            timeout=10.0,
        ) as client:
            buf = make_silent_wav()
            response = await client.post(
                "/transcribe",
                files={"audio": ("test.wav", buf, "audio/wav")},
                data={"session_id": "", "prompt_text": "", "keywords": "", "mode": "auto"},
            )
            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]
            assert "x-session-id" in response.headers


@pytest.mark.asyncio
async def test_status_endpoint_returns_404_for_unknown_session():
    """GET /transcribe/status/{id} returns 404 for unknown session."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/transcribe/status/nonexistent-id")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_cancel_endpoint_removes_session():
    """DELETE /transcribe/{id} returns ok:true for unknown session (idempotent)."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.delete("/transcribe/cancel-id")
        # Unknown session — still returns 200 with ok=True (idempotent)
        assert response.status_code == 200
        assert response.json()["ok"] is True
