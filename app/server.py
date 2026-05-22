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
from fastapi.middleware.cors import CORSMiddleware

# Default port for the FastAPI SSE server — avoids conflict with common dev ports
DEFAULT_PORT = 18763
_SERVER_PORT = int(os.environ.get("TRANSCRIBE_PORT", DEFAULT_PORT))
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app import database as db, network_monitor, transcriber
from app.config import VAULT_PATH

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
    """Format an SSE frame, correctly encoding multi-line data per spec."""
    lines = data.split("\n")
    data_lines = "".join(f"data: {line}\n" for line in lines)
    return f"event: {event}\n{data_lines}\n".encode("utf-8")


# ---------------------------------------------------------------------------
# SSE generator
# ---------------------------------------------------------------------------


async def _transcription_events(
    session_id: str,
    audio_path: Path,
    prompt_text: str,
    keywords: list[str],
    mode: str,
    source: str = "mic",
):
    """Async generator that wraps blocking transcriber.transcribe() via a background thread.

    Yields SSE frames on the "chunk" and "status" events.
    On completion yields: data: [DONE]
    On error yields:     data: [ERROR] <message>
    """
    # Queue items: ("CHUNK", text) | ("STATUS", payload_dict) | None (sentinel)
    queue: asyncio.Queue[tuple[str, str | dict] | None] = asyncio.Queue()

    # Capture the running loop before entering the background thread
    running_loop = asyncio.get_running_loop()

    def chunk_callback(chunk_text: str) -> None:
        """Called from the background transcription thread — push to async queue."""
        # Log chunk reception for ordering debugging
        preview = chunk_text[:40].replace('\n', '\\n')
        logger.debug(
            "[CHUNK-IN] len=%d preview='%s'",
            len(chunk_text), preview,
        )
        running_loop.call_soon_threadsafe(queue.put_nowait, ("CHUNK", chunk_text))

    def status_callback(payload: dict) -> None:
        """Called from the background transcription thread — push status event."""
        logger.debug("[STATUS-IN] phase=%s", payload.get("phase"))
        running_loop.call_soon_threadsafe(queue.put_nowait, ("STATUS", payload))

    def run_transcribe():
        """Execute on a background thread so the event loop is never blocked."""
        print(f"[SERVER] Iniciando transcricao | mode={mode} | source={source}")
        status_callback({"phase": "processing", "message": "Enviando para transcrição..."})
        t = transcriber.Transcriber(is_online_fn=lambda: _net_mon.is_online)
        try:
            t.transcribe(
                audio_path=audio_path,
                prompt_text=prompt_text,
                keywords=keywords,
                mode=mode,  # type: ignore[arg-type]
                on_chunk=chunk_callback,
                source=source,
                on_status=status_callback,
            )
        except Exception as exc:
            logger.error("Transcription error: %s", exc)
            status_callback({"phase": "error", "message": f"Erro: {exc}"})
            running_loop.call_soon_threadsafe(queue.put_nowait, ("CHUNK", f"[ERROR] {exc}"))
        finally:
            running_loop.call_soon_threadsafe(queue.put_nowait, None)

    thread = threading.Thread(target=run_transcribe, daemon=True)
    thread.start()

    with _session_lock:
        _active_sessions[session_id]["status"] = "streaming"

    accumulated = ""
    chunks_received = 0

    try:
        while True:
            item = await queue.get()
            if item is None:
                break

            event_type, payload = item

            # --- Status events: emit immediately ---
            if event_type == "STATUS":
                import json as _json
                yield _sse_frame("status", _json.dumps(payload, ensure_ascii=False))
                continue

            # --- Chunk events: emit immediately ---
            chunk_text = payload  # payload is str for CHUNK
            chunks_received += 1

            # Check for error marker
            if isinstance(chunk_text, str) and chunk_text.startswith("[ERROR]"):
                with _session_lock:
                    if session_id in _active_sessions:
                        _active_sessions[session_id]["status"] = "error"
                yield _sse_frame("chunk", chunk_text)
                break

            # Emit chunk as-is — frontend handles insertion ordering
            accumulated += chunk_text
            with _session_lock:
                if session_id in _active_sessions:
                    _active_sessions[session_id]["accumulated_text"] = accumulated
            yield _sse_frame("chunk", chunk_text)
            logger.debug(
                "[CHUNK-OUT] len=%d preview='%s'",
                len(chunk_text),
                chunk_text[:80].replace("\n", "\\n"),
            )

        # Summary log for debugging
        logger.info(
            "[TRANSCRIPTION-DONE] session=%s received=%d total_chars=%d",
            session_id, chunks_received, len(accumulated),
        )
    except asyncio.CancelledError:
        logger.info("SSE stream cancelled for session %s", session_id)
        with _session_lock:
            if session_id in _active_sessions:
                _active_sessions[session_id]["status"] = "error"
        raise
    finally:
        # Clean up temp audio file
        with _session_lock:
            session_data = _active_sessions.get(session_id, {})
            temp_path_str = session_data.get("temp_path")
            session_status = session_data.get("status", "error")

        if temp_path_str:
            temp_file = Path(temp_path_str)
            # If transcription failed, preserve audio in Vault
            if session_status == "error" and temp_file.exists():
                try:
                    VAULT_PATH.mkdir(parents=True, exist_ok=True)
                    import shutil
                    vault_name = f"transcribe_{session_id[:12]}.wav"
                    shutil.copy2(temp_file, VAULT_PATH / vault_name)
                    logger.info(
                        "Transcription failed — audio preserved in Vault: %s",
                        vault_name,
                    )
                except Exception as e:
                    logger.error("Failed to copy audio to Vault: %s", e)
            temp_file.unlink(missing_ok=True)

    with _session_lock:
        if session_id in _active_sessions:
            _active_sessions[session_id]["status"] = "done"
    logger.info("transcription DONE for session %s", session_id)
    yield _sse_frame("status", '{"phase":"done","message":"Transcrição concluída!"}')
    yield _sse_frame("chunk", "[DONE]")


# ---------------------------------------------------------------------------
# Dual mode helpers
# ---------------------------------------------------------------------------


def _merge_transcriptions(mic_chunks: list[str], sys_chunks: list[str]) -> list[str]:
    """Merge mic and system transcriptions.

    Mic transcription: simple text (user spoke)
    System transcription: with diarization (@Interlocutor X:)

    Strategy: Concatenate with markers. Mic text is marked as @Usuario,
    system text retains its @Interlocutor markers.
    """
    mic_text = "".join(mic_chunks).strip()
    sys_text = "".join(sys_chunks).strip()

    if not mic_text and not sys_text:
        return []

    if not mic_text:
        return [sys_text]

    if not sys_text:
        return [f"@Usuario: {mic_text}"]

    result_parts = []
    if mic_text.strip():
        result_parts.append(f"@Usuario: {mic_text}")
    if sys_text.strip():
        if result_parts:
            result_parts.append("")
        result_parts.append(sys_text)

    merged = "\n\n".join(result_parts)
    return [merged]


async def _transcription_events_dual(
    session_id: str,
    mic_path: Path,
    sys_path: Path,
    prompt_text: str,
    keywords: list[str],
):
    """Async generator for dual mode transcription with merge.

    Runs mic and system transcriptions in parallel threads, waits for both,
    then yields merged transcription chunks.
    """
    queue: asyncio.Queue[tuple[str, str | dict] | None] = asyncio.Queue()
    running_loop = asyncio.get_running_loop()

    mic_chunks: list[str] = []
    sys_chunks: list[str] = []
    mic_done = False
    sys_done = False
    session_status = "streaming"

    def mic_chunk_callback(chunk_text: str) -> None:
        if chunk_text.startswith("[ERROR]"):
            running_loop.call_soon_threadsafe(queue.put_nowait, ("MIC_ERROR", chunk_text))
        else:
            mic_chunks.append(chunk_text)

    def sys_chunk_callback(chunk_text: str) -> None:
        if chunk_text.startswith("[ERROR]"):
            running_loop.call_soon_threadsafe(queue.put_nowait, ("SYS_ERROR", chunk_text))
        else:
            sys_chunks.append(chunk_text)

    def status_callback(payload: dict) -> None:
        running_loop.call_soon_threadsafe(queue.put_nowait, ("STATUS", payload))

    def run_mic_transcribe():
        try:
            t = transcriber.Transcriber(is_online_fn=lambda: _net_mon.is_online)
            t.transcribe(
                audio_path=mic_path,
                prompt_text=prompt_text,
                keywords=keywords,
                mode="gemini",
                on_chunk=mic_chunk_callback,
                source="mic",
                on_status=status_callback,
            )
        except Exception as exc:
            logger.error("Mic transcription error: %s", exc)
            running_loop.call_soon_threadsafe(queue.put_nowait, ("MIC_ERROR", f"[ERROR] {exc}"))
        running_loop.call_soon_threadsafe(queue.put_nowait, ("MIC_DONE", ""))

    def run_sys_transcribe():
        try:
            t = transcriber.Transcriber(is_online_fn=lambda: _net_mon.is_online)
            t.transcribe(
                audio_path=sys_path,
                prompt_text=prompt_text,
                keywords=keywords,
                mode="gemini",
                on_chunk=sys_chunk_callback,
                source="system",
                on_status=status_callback,
            )
        except Exception as exc:
            logger.error("System transcription error: %s", exc)
            running_loop.call_soon_threadsafe(queue.put_nowait, ("SYS_ERROR", f"[ERROR] {exc}"))
        running_loop.call_soon_threadsafe(queue.put_nowait, ("SYS_DONE", ""))

    mic_thread = threading.Thread(target=run_mic_transcribe, daemon=True)
    sys_thread = threading.Thread(target=run_sys_transcribe, daemon=True)
    mic_thread.start()
    sys_thread.start()

    try:
        while not (mic_done and sys_done):
            item = await queue.get()
            if item is None:
                continue

            event_type, payload = item

            if event_type == "STATUS":
                import json as _json
                yield _sse_frame("status", _json.dumps(payload, ensure_ascii=False))

            elif event_type == "MIC_DONE":
                mic_done = True

            elif event_type == "SYS_DONE":
                sys_done = True

            elif event_type == "MIC_ERROR":
                session_status = "error"
                with _session_lock:
                    if session_id in _active_sessions:
                        _active_sessions[session_id]["status"] = "error"
                yield _sse_frame("chunk", payload)
                yield _sse_frame("chunk", "[DONE]")

            elif event_type == "SYS_ERROR":
                session_status = "error"
                with _session_lock:
                    if session_id in _active_sessions:
                        _active_sessions[session_id]["status"] = "error"
                yield _sse_frame("chunk", payload)
                yield _sse_frame("chunk", "[DONE]")

        if session_status == "error":
            logger.info("Dual transcription had errors for session %s", session_id)
            return

        merged_parts = _merge_transcriptions(mic_chunks, sys_chunks)

        accumulated = ""
        for part in merged_parts:
            accumulated += part
            with _session_lock:
                if session_id in _active_sessions:
                    _active_sessions[session_id]["accumulated_text"] = accumulated
            yield _sse_frame("chunk", part)

        logger.info(
            "[DUAL-TRANSCRIPTION-DONE] session=%s mic_chars=%d sys_chars=%d merged_chars=%d",
            session_id, len("".join(mic_chunks)), len("".join(sys_chunks)), len(accumulated),
        )

    except asyncio.CancelledError:
        logger.info("SSE stream cancelled for dual session %s", session_id)
        session_status = "error"
        with _session_lock:
            if session_id in _active_sessions:
                _active_sessions[session_id]["status"] = "error"
        raise
    finally:
        if session_status == "error":
            try:
                import shutil
                preserve_dir = Path.home() / "TranscribeAssistant_DualRecordings"
                preserve_dir.mkdir(parents=True, exist_ok=True)
                short_sid = session_id[:12]
                if mic_path.exists():
                    shutil.copy2(mic_path, preserve_dir / f"failed_{short_sid}_mic.wav")
                if sys_path.exists():
                    shutil.copy2(sys_path, preserve_dir / f"failed_{short_sid}_sys.wav")
                logger.info(
                    "Dual audio preserved for debugging: %s",
                    preserve_dir,
                )
            except Exception as e:
                logger.error("Failed to preserve dual audio: %s", e)

        mic_path.unlink(missing_ok=True)
        sys_path.unlink(missing_ok=True)

    with _session_lock:
        if session_id in _active_sessions:
            _active_sessions[session_id]["status"] = "done"
    logger.info("Dual transcription DONE for session %s", session_id)
    yield _sse_frame("status", '{"phase":"done","message":"Transcricao dual concluida!"}')
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    session_id: Annotated[str | None, Form()] = None,
    prompt_text: Annotated[str, Form()] = "",
    keywords: Annotated[str, Form()] = "",
    mode: Annotated[str, Form()] = "auto",
    source: Annotated[str, Form()] = "mic",
):
    """POST /transcribe — Accept audio file, stream transcription via SSE.

    If session_id is provided and exists, resume that session (D-08).
    """
    print(f"[SERVER] POST /transcribe recebido | mode={mode} | source={source}")
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

    # Wrapper generator that emits initial status events before the main stream
    async def _stream_with_status():
        import json as _json
        yield _sse_frame("status", _json.dumps({"phase": "received", "message": "Áudio recebido, preparando..."}, ensure_ascii=False))
        yield _sse_frame("status", _json.dumps({"phase": "saved", "message": "Arquivo salvo, iniciando processamento..."}, ensure_ascii=False))
        async for frame in _transcription_events(sid, temp_path, prompt_text, keywords_list, mode, source):
            yield frame

    return StreamingResponse(
        _stream_with_status(),
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


@app.post("/transcribe/dual")
async def transcribe_dual(
    mic_audio: UploadFile = File(...),
    sys_audio: UploadFile = File(...),
    session_id: Annotated[str | None, Form()] = None,
    prompt_text: Annotated[str, Form()] = "",
    keywords: Annotated[str, Form()] = "",
):
    """POST /transcribe/dual — Accept two audio files for dual mode transcription.

    Streams merged transcription via SSE.
    """
    print(f"[SERVER] POST /transcribe/dual received")

    MAX_SIZE = 100 * 1024 * 1024  # 100MB per file

    mic_bytes = b""
    while chunk := await mic_audio.read(1024 * 1024):
        mic_bytes += chunk
        if len(mic_bytes) > MAX_SIZE:
            raise HTTPException(status_code=413, detail="Mic audio too large (max 100MB)")
    if len(mic_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty mic audio")

    sys_bytes = b""
    while chunk := await sys_audio.read(1024 * 1024):
        sys_bytes += chunk
        if len(sys_bytes) > MAX_SIZE:
            raise HTTPException(status_code=413, detail="System audio too large (max 100MB)")
    if len(sys_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty system audio")

    sid = session_id or str(uuid.uuid4())

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav", prefix=f"mic_{sid[:8]}_") as f:
        f.write(mic_bytes)
        mic_path = Path(f.name)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav", prefix=f"sys_{sid[:8]}_") as f:
        f.write(sys_bytes)
        sys_path = Path(f.name)

    with _session_lock:
        _active_sessions[sid] = {
            "accumulated_text": "",
            "status": "pending",
            "temp_mic_path": str(mic_path),
            "temp_sys_path": str(sys_path),
        }

    keywords_list = [k.strip() for k in keywords.split(",") if k.strip()] if keywords else []

    logger.info("Starting dual transcription session=%s", sid)

    async def _stream_with_status():
        import json as _json
        yield _sse_frame("status", _json.dumps({"phase": "received", "message": "Audios dual recebidos..."}, ensure_ascii=False))
        async for frame in _transcription_events_dual(sid, mic_path, sys_path, prompt_text, keywords_list):
            yield frame

    return StreamingResponse(
        _stream_with_status(),
        media_type="text/event-stream",
        headers={
            "X-Session-ID": sid,
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


# ---------------------------------------------------------------------------
# Prompt management
# ---------------------------------------------------------------------------

from pydantic import BaseModel as PydanticBaseModel


class PromptResponse(PydanticBaseModel):
    id: int | None = None
    nome: str = ""
    texto_prompt: str = ""
    keywords: list[str] = []


class PromptUpdateRequest(PydanticBaseModel):
    nome: str
    texto_prompt: str
    keywords: list[str]


@app.get("/prompt/default", response_model=PromptResponse)
async def get_default_prompt():
    """GET /prompt/default — Return the default prompt and its keywords."""
    default = db.get_default_prompt()
    if not default:
        return PromptResponse()
    keywords = [
        row["palavra"] for row in db.get_keywords_by_prompt(default["id"])
    ]
    return PromptResponse(
        id=default["id"],
        nome=default["nome"],
        texto_prompt=default["texto_prompt"],
        keywords=keywords,
    )


@app.put("/prompt/default", response_model=PromptResponse)
async def update_default_prompt(body: PromptUpdateRequest):
    """PUT /prompt/default — Update or create the default prompt and keywords."""
    if not body.nome.strip():
        raise HTTPException(status_code=400, detail="Nome nao pode ser vazio")

    default = db.get_default_prompt()
    if default:
        db.update_prompt(default["id"], body.nome, body.texto_prompt, is_default=True)
        pid = default["id"]
    else:
        pid = db.create_prompt(body.nome, body.texto_prompt, is_default=True)

    db.replace_keywords(pid, body.keywords)

    keywords = [
        row["palavra"] for row in db.get_keywords_by_prompt(pid)
    ]
    return PromptResponse(
        id=pid,
        nome=body.nome,
        texto_prompt=body.texto_prompt,
        keywords=keywords,
    )


# ---------------------------------------------------------------------------
# Settings Management
# ---------------------------------------------------------------------------

class SettingsResponse(PydanticBaseModel):
    gemini_key_configured: bool
    gemini_key_masked: str
    gemini_model: str
    groq_key_configured: bool
    groq_key_masked: str
    groq_review_model: str
    app_language: str
    vault_path: str
    dual_intermediary_path: str
    network_ping_host: str
    network_ping_port: int
    network_check_interval: int


class SettingsUpdateRequest(PydanticBaseModel):
    gemini_key: str | None = None
    gemini_model: str | None = None
    groq_key: str | None = None
    groq_review_model: str | None = None
    app_language: str | None = None
    vault_path: str | None = None
    dual_intermediary_path: str | None = None
    network_ping_host: str | None = None
    network_ping_port: int | None = None
    network_check_interval: int | None = None


class FetchModelsRequest(PydanticBaseModel):
    gemini_key: str | None = None
    groq_key: str | None = None


class FetchModelsResponse(PydanticBaseModel):
    gemini_models: list[str]
    groq_models: list[str]


def _get_masked_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "********"
    return f"{key[:6]}...{key[-4:]}"


@app.get("/settings", response_model=SettingsResponse)
async def get_settings():
    """GET /settings — Retrieve current application configurations with masked keys."""
    import app.config as config
    config.load_all_settings()
    return SettingsResponse(
        gemini_key_configured=bool(config.GOOGLE_API_KEY),
        gemini_key_masked=_get_masked_key(config.GOOGLE_API_KEY),
        gemini_model=config.GEMINI_MODEL,
        groq_key_configured=bool(config.GROQ_API_KEY),
        groq_key_masked=_get_masked_key(config.GROQ_API_KEY),
        groq_review_model=config.GROQ_REVIEW_MODEL,
        app_language=config.APP_LANGUAGE,
        vault_path=str(config.VAULT_PATH),
        dual_intermediary_path=str(config.DUAL_INTERMEDIARY_PATH),
        network_ping_host=config.NETWORK_PING_HOST,
        network_ping_port=config.NETWORK_PING_PORT,
        network_check_interval=config.NETWORK_CHECK_INTERVAL,
    )


@app.put("/settings", response_model=CancelResponse)
async def update_settings(body: SettingsUpdateRequest):
    """PUT /settings — Update application configurations, encrypting keys if updated."""
    import app.config as config
    import app.database as db
    import app.security as sec

    # Read current keys to handle masking logic
    config.load_all_settings()

    # 1. Gemini Key
    if body.gemini_key is not None:
        gkey = body.gemini_key.strip()
        if "..." in gkey or "********" in gkey or (len(gkey) > 0 and gkey.endswith("XXXX")):
            pass
        elif gkey == "":
            db.set_setting("GOOGLE_API_KEY", "")
        else:
            db.set_setting("GOOGLE_API_KEY", sec.encrypt_value(gkey))

    # 2. Gemini Model
    if body.gemini_model is not None:
        db.set_setting("GEMINI_MODEL", body.gemini_model.strip())

    # 3. Groq Key
    if body.groq_key is not None:
        gqkey = body.groq_key.strip()
        if "..." in gqkey or "********" in gqkey or (len(gqkey) > 0 and gqkey.endswith("XXXX")):
            pass
        elif gqkey == "":
            db.set_setting("GROQ_API_KEY", "")
        else:
            db.set_setting("GROQ_API_KEY", sec.encrypt_value(gqkey))

    # 4. Groq Review Model
    if body.groq_review_model is not None:
        db.set_setting("GROQ_REVIEW_MODEL", body.groq_review_model.strip())

    # 5. Language
    if body.app_language is not None:
        db.set_setting("APP_LANGUAGE", body.app_language.strip())

    # 6. Paths
    if body.vault_path is not None:
        db.set_setting("VAULT_PATH", body.vault_path.strip())
    if body.dual_intermediary_path is not None:
        db.set_setting("DUAL_INTERMEDIARY_PATH", body.dual_intermediary_path.strip())

    # 7. Network
    if body.network_ping_host is not None:
        db.set_setting("NETWORK_PING_HOST", body.network_ping_host.strip())
    if body.network_ping_port is not None:
        db.set_setting("NETWORK_PING_PORT", str(body.network_ping_port))
    if body.network_check_interval is not None:
        db.set_setting("NETWORK_CHECK_INTERVAL", str(body.network_check_interval))

    # Propagate changes to config in-memory globals
    config.reload_config()

    return CancelResponse(ok=True, message="Configurações salvas com sucesso")


@app.post("/settings/models", response_model=FetchModelsResponse)
async def fetch_models(body: FetchModelsRequest):
    """POST /settings/models — Dynamically fetch models available for Gemini and Groq."""
    import app.config as config
    from app.models_fetcher import fetch_gemini_models, fetch_groq_models

    config.load_all_settings()

    # Determine Gemini Key
    gemini_key = body.gemini_key
    if gemini_key is not None:
        gemini_key = gemini_key.strip()
        if "..." in gemini_key or "********" in gemini_key or gemini_key == "":
            gemini_key = config.GOOGLE_API_KEY
    else:
        gemini_key = config.GOOGLE_API_KEY

    # Determine Groq Key
    groq_key = body.groq_key
    if groq_key is not None:
        groq_key = groq_key.strip()
        if "..." in groq_key or "********" in groq_key or groq_key == "":
            groq_key = config.GROQ_API_KEY
    else:
        groq_key = config.GROQ_API_KEY

    # Fetch models
    gemini_list = fetch_gemini_models(gemini_key)
    groq_list = fetch_groq_models(groq_key)

    return FetchModelsResponse(
        gemini_models=gemini_list,
        groq_models=groq_list
    )


# Allow `python -m app.server` or `uvicorn app.server:app`
if __name__ == "__main__":
    import uvicorn
    print(f"Starting Transcribe SSE server on port {_SERVER_PORT}")
    uvicorn.run("app.server:app", host="127.0.0.1", port=_SERVER_PORT, reload=False)
