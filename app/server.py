"""app/server.py — FastAPI SSE wrapper for the transcription engine.

POST /transcribe        — Accepts audio file upload, streams transcription chunks via SSE.
GET  /transcribe/status/{session_id} — Returns accumulated text + status for a session.
DELETE /transcribe/{session_id}      — Cancels a session (idempotent).
"""

import asyncio
import logging
import os
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

# Default port for the FastAPI SSE server — avoids conflict with common dev ports
DEFAULT_PORT = 18763
_SERVER_PORT = int(os.environ.get("TRANSCRIBE_PORT", DEFAULT_PORT))
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app import database as db, network_monitor, transcriber

logger = logging.getLogger("app.server")

# Shared network monitor — start once at module load so is_online is meaningful
_net_mon = network_monitor.NetworkMonitor()
_net_mon.start()

# Ensure DB schema exists at module load
db.initialize_db()

# In-memory session registry (D-08: enables resume on reconnect)
_active_sessions: dict[str, dict] = {}
_session_lock = threading.Lock()


# ---------------------------------------------------------------------------
# SSE helper
# ---------------------------------------------------------------------------


def _sse_frame(event: str, data: str) -> bytes:
    """Format an SSE frame."""
    return f"event: {event}\ndata: {data}\n\n".encode("utf-8")


# ---------------------------------------------------------------------------
# SSE generator
# ---------------------------------------------------------------------------


async def _transcription_events(
    session_id: str,
    audio_path: Path,
    prompt_text: str,
    keywords: list[str],
    mode: str,
):
    """Async generator that wraps blocking transcriber.transcribe() via a background thread.

    Yields SSE frames on the "chunk" event.
    On completion yields: data: [DONE]
    On error yields:     data: [ERROR] <message>
    """
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    # Capture the running loop before entering the background thread
    running_loop = asyncio.get_running_loop()

    def chunk_callback(chunk_text: str) -> None:
        """Called from the background transcription thread — push to async queue."""
        running_loop.call_soon_threadsafe(queue.put_nowait, chunk_text)

    def run_transcribe():
        """Execute on a background thread so the event loop is never blocked."""
        t = transcriber.Transcriber(is_online_fn=lambda: _net_mon.is_online)
        try:
            t.transcribe(
                audio_path=audio_path,
                prompt_text=prompt_text,
                keywords=keywords,
                mode=mode,  # type: ignore[arg-type]
                on_chunk=chunk_callback,
            )
        except Exception as exc:
            logger.error("Transcription error: %s", exc)
            running_loop.call_soon_threadsafe(queue.put_nowait, f"[ERROR] {exc}")
        finally:
            running_loop.call_soon_threadsafe(queue.put_nowait, None)

    thread = threading.Thread(target=run_transcribe, daemon=True)
    thread.start()

    with _session_lock:
        _active_sessions[session_id]["status"] = "streaming"

    accumulated = ""

    try:
        while True:
            item = await queue.get()
            if item is None:
                break
            accumulated += item
            with _session_lock:
                if session_id in _active_sessions:
                    _active_sessions[session_id]["accumulated_text"] = accumulated
            yield _sse_frame("chunk", item)
            logger.debug("chunk: %s", item[:50])
    except asyncio.CancelledError:
        logger.info("SSE stream cancelled for session %s", session_id)
        with _session_lock:
            if session_id in _active_sessions:
                _active_sessions[session_id]["status"] = "error"
        raise
    finally:
        # Clean up temp audio file
        with _session_lock:
            temp_path_str = _active_sessions.get(session_id, {}).get("temp_path")
        if temp_path_str:
            Path(temp_path_str).unlink(missing_ok=True)

    with _session_lock:
        if session_id in _active_sessions:
            _active_sessions[session_id]["status"] = "done"
    logger.info("transcription DONE for session %s", session_id)
    yield _sse_frame("chunk", "[DONE]")


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class TranscriptionStatusResponse(BaseModel):
    session_id: str | None
    accumulated_text: str
    status: str  # "streaming" | "done" | "error"


class CancelResponse(BaseModel):
    ok: bool
    message: str


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="Transcribe Assistant API")


@app.post("/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    session_id: Annotated[str | None, Form()] = None,
    prompt_text: Annotated[str, Form()] = "",
    keywords: Annotated[str, Form()] = "",
    mode: Annotated[str, Form()] = "auto",
):
    """POST /transcribe — Accept audio file, stream transcription via SSE.

    If session_id is provided and exists, resume that session (D-08).
    """
    # Read in chunks to enforce 100MB limit without loading full file into RAM
    MAX_SIZE = 100 * 1024 * 1024
    audio_bytes = b""
    while chunk := await audio.read(1024 * 1024):  # 1MB chunks
        audio_bytes += chunk
        if len(audio_bytes) > MAX_SIZE:
            raise HTTPException(status_code=413, detail="File too large (max 100MB)")
    if len(audio_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty audio file")

    # Persist to a temp file consumed by the transcriber
    suffix = Path(audio.filename).suffix if audio.filename else ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
        f.write(audio_bytes)
        temp_path = Path(f.name)

    # Resolve or create session
    sid = session_id if (session_id and session_id in _active_sessions) else None
    if sid is None:
        sid = str(uuid.uuid4())

    with _session_lock:
        _active_sessions[sid] = {"accumulated_text": "", "status": "pending", "temp_path": str(temp_path)}

    keywords_list = [k.strip() for k in keywords.split(",") if k.strip()] if keywords else []

    logger.info("Starting transcription session=%s mode=%s", sid, mode)

    return StreamingResponse(
        _transcription_events(sid, temp_path, prompt_text, keywords_list, mode),
        media_type="text/event-stream",
        headers={
            "X-Session-ID": sid,
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@app.get("/transcribe/status/{session_id}", response_model=TranscriptionStatusResponse)
async def get_status(session_id: str):
    """GET /transcribe/status/{session_id} — Return accumulated text + status."""
    with _session_lock:
        if session_id not in _active_sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        session = _active_sessions[session_id]
    return TranscriptionStatusResponse(
        session_id=session_id,
        accumulated_text=session["accumulated_text"],
        status=session["status"],
    )


@app.delete("/transcribe/{session_id}", response_model=CancelResponse)
async def cancel_session(session_id: str):
    """DELETE /transcribe/{session_id} — Cancel / forget a session (idempotent)."""
    with _session_lock:
        temp_path_str = _active_sessions.pop(session_id, {}).get("temp_path")
    if temp_path_str:
        Path(temp_path_str).unlink(missing_ok=True)
    return CancelResponse(ok=True, message="Session cancelled")


# Allow `python -m app.server` or `uvicorn app.server:app`
if __name__ == "__main__":
    import uvicorn
    print(f"Starting Transcribe SSE server on port {_SERVER_PORT}")
    uvicorn.run("app.server:app", host="127.0.0.1", port=_SERVER_PORT, reload=False)
