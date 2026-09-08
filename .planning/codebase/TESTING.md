# Testing Patterns

**Analysis Date:** 2026-04-14

## Test Framework

**Python:**
- Runner: pytest 8.0+
- Async: pytest-asyncio 0.25.0+
- HTTP: httpx 0.28.0 (ASGITransport for FastAPI testing)

**Dev Dependencies (from `pyproject.toml`):**
```toml
[dependency-groups]
dev = [
    "black>=26.1.0",
    "httpx>=0.28.0",
    "pytest>=8.0",
    "pytest-asyncio>=0.25.0",
]
```

**Run Commands:**
```bash
pytest                          # Run all tests
pytest tests/test_server_sse.py  # Run specific file
```

## Test File Organization

**Location:** `tests/` directory at project root

**Naming:** `test_*.py` pattern

**Current Test Files:**
- `tests/test_server_sse.py` — SSE endpoint tests

## Test Structure

**FastAPI SSE Testing Pattern:**
```python
from httpx import ASGITransport, AsyncClient

@pytest.mark.asyncio
async def test_transcribe_endpoint_returns_sse_media_type():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        timeout=10.0,
    ) as client:
        response = await client.post("/transcribe", ...)
```

**Fixtures:**
```python
@pytest.fixture(autouse=True)
def setup_db():
    initialize_db()
    yield
```

## Mocking Patterns

**Async Generator Mocking:**
```python
async def mock_transcribe_events(session_id, audio_path, prompt_text, keywords, mode):
    from app.server import _sse_frame
    yield _sse_frame("chunk", "test chunk")
    yield _sse_frame("chunk", "[DONE]")

with patch("app.server._transcription_events", mock_transcribe_events):
    ...
```

**Mock Targets:**
- `app.server._transcription_events` — SSE stream generation
- `app.transcriber.Transcriber` — transcription logic
- `google.genai` client — cloud transcription

## Audio Testing

**Challenges:**
- Real transcription is slow (depends on model loading)
- Hardware-dependent (microphone, speakers)

**Approach:**
- Mock transcription layer entirely
- Test audio format parsing with synthetic WAV files
- Test file upload size limits

**WAV Fixture Pattern:**
```python
def make_silent_wav() -> io.BytesIO:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(struct.pack("<h", 0) * 44100)
    buf.seek(0)
    return buf
```

## Current Test Coverage

**Covered:**
- `/transcribe` endpoint — SSE content-type validation
- `/transcribe/status/{session_id}` — 404 for unknown sessions
- `/transcribe/{session_id}` (DELETE) — idempotent cancel behavior

**Not Covered:**
- Database operations
- Audio recording hardware
- Transcription engine accuracy
- Electron IPC handlers

## CI/CD

**Status:** Not configured
- No GitHub Actions workflows
- No automated test pipeline

---

*Testing analysis: 2026-04-14*