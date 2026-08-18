"""app/server.py — FastAPI SSE wrapper for the transcription engine.

POST /transcribe        — Accepts audio file upload, streams transcription chunks via SSE.
GET  /transcribe/status/{session_id} — Returns accumulated text + status for a session.
DELETE /transcribe/{session_id}      — Cancels a session (idempotent).
"""

import asyncio
import json
import logging
import os
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import socketio

# Default port for the FastAPI server
DEFAULT_PORT = 18763
_SERVER_PORT = int(os.environ.get("TRANSCRIBE_PORT", DEFAULT_PORT))
from pydantic import BaseModel

from app import database as db, network_monitor, transcriber
from app.audio_recorder import AudioRecorder
from app.config import VAULT_PATH
from app.job_worker import TranscriptionJobWorker

# Socket.IO setup
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=['http://localhost:5173'],
    max_http_buffer_size=1048576,
    ping_timeout=20,
    ping_interval=25,
)

@sio.event
async def connect(sid, environ, auth):
    logger.info("[Socket.IO] Client connected: %s", sid)

@sio.event
async def disconnect(sid):
    logger.info("[Socket.IO] Client disconnected: %s", sid)

@sio.on('transcription:cancel')
async def on_cancel(sid, data):
    session_id = data.get('sessionId')
    if session_id:
        with _session_lock:
            if session_id in _active_sessions:
                _active_sessions[session_id]["status"] = "cancelled"
        await sio.emit('transcription:status', {"phase": "cancelled", "message": "Cancelado.", "sessionId": session_id}, to=sid)
        logger.info("[Socket.IO] Transcription cancelled: %s", session_id)


logger = logging.getLogger("app.server")

# Shared network monitor — wake the durable queue as soon as connectivity returns.
def _on_network_change(online: bool) -> None:
    if online and _job_worker:
        _job_worker.wake()


_net_mon = network_monitor.NetworkMonitor(on_status_change=_on_network_change)
_net_mon.start()

# Ensure DB schema exists at module load
db.initialize_db()

# In-memory session registry (D-08: enables resume on reconnect)
_active_sessions: dict[str, dict] = {}
_session_lock = threading.Lock()


# ---------------------------------------------------------------------------
# SSE helper
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Background tasks for Socket.IO emission
# ---------------------------------------------------------------------------

async def _emit_transcription_task(
    session_id: str,
    audio_path: Path,
    prompt_text: str,
    keywords: list[str],
    mode: str,
    source: str,
    client_sid: str,
):
    queue = asyncio.Queue()
    running_loop = asyncio.get_running_loop()

    def chunk_callback(chunk_text: str) -> None:
        preview = chunk_text[:40].replace('\n', '\\n')
        logger.debug("[CHUNK-IN] len=%d preview='%s'", len(chunk_text), preview)
        running_loop.call_soon_threadsafe(queue.put_nowait, ("CHUNK", chunk_text))

    def status_callback(payload: dict) -> None:
        payload["sessionId"] = session_id
        logger.debug("[STATUS-IN] phase=%s", payload.get("phase"))
        running_loop.call_soon_threadsafe(queue.put_nowait, ("STATUS", payload))

    def run_transcribe():
        print(f"[SERVER] Iniciando transcricao | mode={mode} | source={source}")
        status_callback({"phase": "processing", "message": "Enviando para transcrição..."})
        t = transcriber.Transcriber(is_online_fn=lambda: _net_mon.is_online)
        try:
            t.transcribe(
                audio_path=audio_path,
                prompt_text=prompt_text,
                keywords=keywords,
                mode=mode,
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
        seq_counter = _active_sessions[session_id].get("seq_counter", 0)

    accumulated = ""
    chunks_received = 0
    session_status = "done"

    try:
        while True:
            item = await queue.get()
            if item is None:
                break

            with _session_lock:
                if _active_sessions.get(session_id, {}).get("status") == "cancelled":
                    session_status = "cancelled"
                    break

            event_type, payload = item

            if event_type == "STATUS":
                await sio.emit("transcription:status", payload, to=client_sid)
                continue

            chunk_text = payload
            chunks_received += 1

            if isinstance(chunk_text, str) and chunk_text.startswith("[ERROR]"):
                session_status = "error"
                with _session_lock:
                    if session_id in _active_sessions:
                        _active_sessions[session_id]["status"] = "error"
                await sio.emit("transcription:error", {"sessionId": session_id, "message": chunk_text}, to=client_sid)
                break

            accumulated += chunk_text
            with _session_lock:
                if session_id in _active_sessions:
                    _active_sessions[session_id]["accumulated_text"] = accumulated
                    seq_counter = _active_sessions[session_id]["seq_counter"]
                    _active_sessions[session_id]["seq_counter"] += 1

            logger.debug("[CHUNK-OUT] emitting seq=%d len=%d", seq_counter, len(chunk_text))
            
            # Emit with ACK
            try:
                ack = await sio.call('transcription:chunk', {
                    'seq': seq_counter,
                    'text': chunk_text,
                    'sessionId': session_id
                }, to=client_sid, timeout=10)
                logger.debug("[CHUNK-ACK] seq=%d ack=%s", seq_counter, ack)
            except socketio.exceptions.TimeoutError:
                logger.error("[CHUNK-ACK-TIMEOUT] Client did not ack chunk seq=%d", seq_counter)
                session_status = "error"
                await sio.emit("transcription:error", {"sessionId": session_id, "message": "Timeout aguardando editor"}, to=client_sid)
                break

        logger.info("[TRANSCRIPTION-DONE] session=%s received=%d total_chars=%d", session_id, chunks_received, len(accumulated))
    except asyncio.CancelledError:
        logger.info("Task cancelled for session %s", session_id)
        session_status = "error"
        with _session_lock:
            if session_id in _active_sessions:
                _active_sessions[session_id]["status"] = "error"
        raise
    finally:
        with _session_lock:
            session_data = _active_sessions.get(session_id, {})
            temp_path_str = session_data.get("temp_path")
            if session_id in _active_sessions and _active_sessions[session_id]["status"] != "cancelled":
                _active_sessions[session_id]["status"] = session_status

        if temp_path_str:
            temp_file = Path(temp_path_str)
            if session_status == "error" and temp_file.exists():
                try:
                    VAULT_PATH.mkdir(parents=True, exist_ok=True)
                    import shutil
                    vault_name = f"transcribe_{session_id[:12]}.wav"
                    shutil.copy2(temp_file, VAULT_PATH / vault_name)
                except Exception as e:
                    logger.error("Failed to copy audio to Vault: %s", e)
            temp_file.unlink(missing_ok=True)

    if session_status == "done":
        await sio.emit("transcription:status", {"phase": "done", "message": "Transcrição concluída!", "sessionId": session_id}, to=client_sid)
        await sio.emit("transcription:done", {"sessionId": session_id, "totalChunks": chunks_received}, to=client_sid)


async def _emit_transcription_task_dual(
    session_id: str,
    mic_path: Path,
    sys_path: Path,
    prompt_text: str,
    keywords: list[str],
    client_sid: str,
):
    queue = asyncio.Queue()
    running_loop = asyncio.get_running_loop()

    def chunk_callback(chunk_text: str) -> None:
        running_loop.call_soon_threadsafe(queue.put_nowait, ("CHUNK", chunk_text))

    def status_callback(payload: dict) -> None:
        payload["sessionId"] = session_id
        running_loop.call_soon_threadsafe(queue.put_nowait, ("STATUS", payload))

    def run_transcribe():
        print(f"[SERVER] Iniciando transcrição Dual | session={session_id}")
        status_callback({"phase": "processing", "message": "Enviando áudios para transcrição dual..."})
        t = transcriber.Transcriber(is_online_fn=lambda: _net_mon.is_online)
        try:
            t.transcribe(
                audio_path=[mic_path, sys_path],
                prompt_text=prompt_text,
                keywords=keywords,
                mode="gemini",
                on_chunk=chunk_callback,
                source="dual",
                on_status=status_callback,
            )
        except Exception as exc:
            logger.error("Dual transcription error: %s", exc)
            status_callback({"phase": "error", "message": f"Erro: {exc}"})
            running_loop.call_soon_threadsafe(queue.put_nowait, ("CHUNK", f"[ERROR] {exc}"))
        finally:
            running_loop.call_soon_threadsafe(queue.put_nowait, None)

    thread = threading.Thread(target=run_transcribe, daemon=True)
    thread.start()

    with _session_lock:
        if session_id in _active_sessions:
            _active_sessions[session_id]["status"] = "streaming"
            seq_counter = _active_sessions[session_id].get("seq_counter", 0)

    accumulated = ""
    chunks_received = 0
    session_status = "done"

    try:
        while True:
            item = await queue.get()
            if item is None:
                break

            with _session_lock:
                if _active_sessions.get(session_id, {}).get("status") == "cancelled":
                    session_status = "cancelled"
                    break

            event_type, payload = item

            if event_type == "STATUS":
                await sio.emit("transcription:status", payload, to=client_sid)
                continue

            chunk_text = payload
            chunks_received += 1

            if isinstance(chunk_text, str) and chunk_text.startswith("[ERROR]"):
                session_status = "error"
                with _session_lock:
                    if session_id in _active_sessions:
                        _active_sessions[session_id]["status"] = "error"
                await sio.emit("transcription:error", {"sessionId": session_id, "message": chunk_text}, to=client_sid)
                break

            accumulated += chunk_text
            with _session_lock:
                if session_id in _active_sessions:
                    _active_sessions[session_id]["accumulated_text"] = accumulated
                    seq_counter = _active_sessions[session_id]["seq_counter"]
                    _active_sessions[session_id]["seq_counter"] += 1

            try:
                ack = await sio.call('transcription:chunk', {
                    'seq': seq_counter,
                    'text': chunk_text,
                    'sessionId': session_id
                }, to=client_sid, timeout=10)
            except socketio.exceptions.TimeoutError:
                logger.error("[DUAL-CHUNK-ACK-TIMEOUT] seq=%d", seq_counter)
                session_status = "error"
                await sio.emit("transcription:error", {"sessionId": session_id, "message": "Timeout aguardando editor"}, to=client_sid)
                break

    except asyncio.CancelledError:
        logger.info("Task cancelled for dual session %s", session_id)
        session_status = "error"
        with _session_lock:
            if session_id in _active_sessions:
                _active_sessions[session_id]["status"] = "error"
        raise
    finally:
        if session_status == "error":
            try:
                VAULT_PATH.mkdir(parents=True, exist_ok=True)
                import shutil
                short_sid = session_id[:12]
                if mic_path.exists():
                    shutil.copy2(mic_path, VAULT_PATH / f"transcribe_dual_{short_sid}_mic.wav")
                if sys_path.exists():
                    shutil.copy2(sys_path, VAULT_PATH / f"transcribe_dual_{short_sid}_sys.wav")
            except Exception as e:
                logger.error("Failed to copy dual audio to Vault: %s", e)

        mic_path.unlink(missing_ok=True)
        sys_path.unlink(missing_ok=True)

        with _session_lock:
            if session_id in _active_sessions and _active_sessions[session_id]["status"] != "cancelled":
                _active_sessions[session_id]["status"] = session_status

    if session_status == "done":
        await sio.emit("transcription:status", {"phase": "done", "message": "Transcrição dual concluída!", "sessionId": session_id}, to=client_sid)
        await sio.emit("transcription:done", {"sessionId": session_id, "totalChunks": chunks_received}, to=client_sid)

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
_job_worker: TranscriptionJobWorker | None = None


async def _emit_job_event(event: str, payload: dict) -> None:
    """Best-effort notification; persisted job state remains authoritative."""
    job = db.get_transcription_job(payload.get("sessionId", ""))
    target = job["client_sid"] if job and "client_sid" in job.keys() else None
    await sio.emit(event, payload, to=target)


@app.on_event("startup")
async def start_job_worker() -> None:
    global _job_worker
    # Crash recovery: convert orphaned progressive captures into playable WAVs.
    recovered = AudioRecorder.recover_pcm_parts(
        VAULT_PATH / "recordings" / "pending", logger=logger.warning
    )
    if recovered:
        logger.warning("[Startup] %d interrupted recording(s) recovered to Vault", len(recovered))
    _job_worker = TranscriptionJobWorker(
        is_online_fn=lambda: _net_mon.is_online,
        emit=_emit_job_event,
    )
    _job_worker.start()


@app.on_event("shutdown")
async def stop_job_worker() -> None:
    if _job_worker:
        await _job_worker.stop()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Wrap the FastAPI app in the Socket.IO ASGI App
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)


# ---------------------------------------------------------------------------
# Durable transcription jobs (SQLite-backed queue)
# ---------------------------------------------------------------------------


class TranscribeJobRequest(BaseModel):
    audio_paths: list[str]
    prompt_text: str = ""
    keywords: str = ""
    mode: str = "auto"  # auto | gemini | groq
    source: str = "mic"  # mic | system | dual
    socket_id: str = ""


def _validate_recording_paths(paths: list[str]) -> list[Path]:
    """Only files inside Vault/recordings may be queued — never arbitrary paths."""
    recordings_root = (VAULT_PATH / "recordings").resolve()
    resolved = []
    for p in paths:
        rp = Path(p).resolve()
        if not str(rp).startswith(str(recordings_root)):
            raise HTTPException(status_code=400, detail=f"Path fora do Vault: {p}")
        resolved.append(rp)
    if not resolved:
        raise HTTPException(status_code=400, detail="audio_paths vazio")
    return resolved


@app.post("/transcribe/import")
async def transcribe_import(
    audio: UploadFile = File(...),
    prompt_text: Annotated[str, Form()] = "",
    keywords: Annotated[str, Form()] = "",
    mode: Annotated[str, Form()] = "gemini",
    source: Annotated[str, Form()] = "import",
    x_socket_id: str | None = Header(None, alias="X-Socket-ID"),
):
    """Copy an imported file into durable Vault storage, then queue it."""
    pending = VAULT_PATH / "recordings" / "pending"
    pending.mkdir(parents=True, exist_ok=True)
    suffix = Path(audio.filename or "audio.wav").suffix or ".wav"
    path = pending / f"import_{uuid.uuid4().hex[:12]}{suffix}"
    size = 0
    try:
        with open(path, "xb") as target:
            while chunk := await audio.read(1024 * 1024):
                size += len(chunk)
                if size > 500 * 1024 * 1024:
                    raise HTTPException(status_code=413, detail="Arquivo maior que 500 MB")
                target.write(chunk)
            target.flush()
            os.fsync(target.fileno())
        if size == 0:
            raise HTTPException(status_code=400, detail="Arquivo vazio")
        body = TranscribeJobRequest(
            audio_paths=[str(path)], prompt_text=prompt_text, keywords=keywords,
            mode=mode, source=source, socket_id=x_socket_id or "",
        )
        return await transcribe(body)
    except Exception:
        if size == 0:
            path.unlink(missing_ok=True)
        raise


@app.post("/transcribe")
async def transcribe(body: TranscribeJobRequest):
    """POST /transcribe — Queue a durable transcription job for local audio files."""
    paths = _validate_recording_paths(body.audio_paths)
    missing = [str(p) for p in paths if not p.exists()]
    if missing:
        raise HTTPException(status_code=400, detail=f"Áudio não encontrado: {missing}")

    job_id = str(uuid.uuid4())
    keywords = [k.strip() for k in body.keywords.split(",") if k.strip()] if body.keywords else []
    db.create_transcription_job(
        job_id,
        audio_paths=json.dumps([str(p) for p in paths]),
        source=body.source,
        mode=body.mode,
        prompt_text=body.prompt_text,
        keywords=json.dumps(keywords),
        client_sid=body.socket_id or None,
    )
    logger.info("Queued job=%s mode=%s source=%s files=%d", job_id, body.mode, body.source, len(paths))
    if _job_worker:
        _job_worker.wake()
    return JSONResponse(content={"sessionId": job_id, "status": "queued"}, status_code=202)


@app.get("/jobs/{job_id}")
async def get_job(job_id: str):
    """GET /jobs/{job_id} — Authoritative job state for UI reconciliation."""
    job = db.get_transcription_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    return {
        "id": job["id"],
        "status": job["status"],
        "provider": job["provider"],
        "text": job["accumulated_text"],
        "lastError": job["last_error"],
        "nextRetryAt": job["next_retry_at"],
        "audioPaths": json.loads(job["audio_paths"]),
        "updatedAt": job["updated_at"],
    }


@app.post("/jobs/{job_id}/retry")
async def retry_job(job_id: str, body: TranscribeJobRequest | None = None):
    """POST /jobs/{job_id}/retry — Requeue a failed job. Audio is never deleted."""
    job = db.get_transcription_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    if job["status"] not in ("failed_retryable", "failed_permanent", "retry_wait", "cancelled"):
        raise HTTPException(status_code=409, detail=f"Job em estado não-retentável: {job['status']}")
    update: dict = {"status": "queued", "next_retry_at": None, "last_error": None}
    if body and body.socket_id:
        update["client_sid"] = body.socket_id
    db.update_transcription_job(job_id, **update)
    if _job_worker:
        _job_worker.wake()
    return {"ok": True, "status": "queued"}


@app.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    """POST /jobs/{job_id}/cancel — Stop processing; audio is never deleted."""
    job = db.get_transcription_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    if job["status"] in ("completed", "cancelled"):
        return {"ok": True, "status": job["status"]}
    if _job_worker and job["status"].startswith("processing"):
        _job_worker.cancel_job(job_id)
    else:
        db.update_transcription_job(job_id, status="cancelled")
    return {"ok": True, "status": "cancelled"}


@app.get("/transcribe/status/{session_id}", response_model=TranscriptionStatusResponse)
async def get_status(session_id: str):
    """GET /transcribe/status/{session_id} — Back-compat view over the jobs table."""
    job = db.get_transcription_job(session_id)
    if not job:
        raise HTTPException(status_code=404, detail="Session not found")
    return TranscriptionStatusResponse(
        session_id=session_id,
        accumulated_text=job["accumulated_text"],
        status=job["status"],
    )


@app.delete("/transcribe/{session_id}", response_model=CancelResponse)
async def cancel_session(session_id: str):
    """DELETE /transcribe/{session_id} — Cancel a job (idempotent, audio preserved)."""
    job = db.get_transcription_job(session_id)
    if not job:
        raise HTTPException(status_code=404, detail="Session not found")
    if job["status"] in ("completed", "cancelled"):
        return CancelResponse(ok=True, message=f"Job already {job['status']}")
    if _job_worker and job["status"].startswith("processing"):
        _job_worker.cancel_job(session_id)
    else:
        db.update_transcription_job(session_id, status="cancelled")
    return CancelResponse(ok=True, message="Cancelled")


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
    tray_enabled: bool
    persistent_notifications_enabled: bool
    alert_interval: int
    alert_transcription_types: str


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
    tray_enabled: bool | None = None
    persistent_notifications_enabled: bool | None = None
    alert_interval: int | None = None
    alert_transcription_types: str | None = None


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
        tray_enabled=config.TRAY_ENABLED,
        persistent_notifications_enabled=config.PERSISTENT_NOTIFICATIONS_ENABLED,
        alert_interval=config.ALERT_INTERVAL,
        alert_transcription_types=config.ALERT_TRANSCRIPTION_TYPES,
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

    # 8. Tray & Alerts
    if body.tray_enabled is not None:
        db.set_setting("TRAY_ENABLED", str(body.tray_enabled))
    if body.persistent_notifications_enabled is not None:
        db.set_setting("PERSISTENT_NOTIFICATIONS_ENABLED", str(body.persistent_notifications_enabled))
    if body.alert_interval is not None:
        db.set_setting("ALERT_INTERVAL", str(body.alert_interval))
    if body.alert_transcription_types is not None:
        db.set_setting("ALERT_TRANSCRIPTION_TYPES", body.alert_transcription_types.strip())

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


# ---------------------------------------------------------------------------
# Streaming ASR (Socket.IO & REST Chunking)
# ---------------------------------------------------------------------------
from app.agents import StreamAlignmentAgent

# In-memory registry for active streaming sessions
_streaming_sessions: dict[str, dict] = {}
_streaming_sessions_lock = threading.Lock()

@sio.on('transcription:stream:cancel')
async def on_stream_cancel(sid, data):
    session_id = data.get('sessionId')
    if session_id:
        with _streaming_sessions_lock:
            if session_id in _streaming_sessions:
                _streaming_sessions[session_id]["status"] = "cancelled"
                logger.info("[Socket.IO] Streaming session cancelled: %s", session_id)


@app.post("/transcribe/stream/{session_id}/chunk")
async def receive_stream_chunk(
    session_id: str,
    request: Request,
    prompt_text: str = "",
    keywords: str = "",
    socket_id: str = "",
):
    """POST /transcribe/stream/{session_id}/chunk — Accepts audio chunk upload, transcribes, aligns, and streams back to client via Socket.IO."""
    # Register the session dynamically if it's the first chunk
    with _streaming_sessions_lock:
        if session_id not in _streaming_sessions:
            _streaming_sessions[session_id] = {
                "consolidated_text": "",
                "last_raw_whisper": "",
                "agent": StreamAlignmentAgent(),
                "status": "active"
            }
        session = _streaming_sessions[session_id]
        if session["status"] == "cancelled":
            return {"status": "cancelled"}

    # Read raw bytes from the request body (WAV file)
    chunk_bytes = await request.body()
    if not chunk_bytes:
        raise HTTPException(status_code=400, detail="Empty audio chunk")

    # Run the transcription and alignment in a background thread
    loop = asyncio.get_running_loop()

    def run_whisper_and_align():
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp.write(chunk_bytes)
            tmp_path = Path(tmp.name)

        try:
            t = transcriber.Transcriber(is_online_fn=lambda: _net_mon.is_online)
            keywords_list = [k.strip() for k in keywords.split(",") if k.strip()] if keywords else []
            
            raw_text = t.transcribe_raw_groq(tmp_path, keywords_list)
            logger.info(f"[Stream ASR] Raw Whisper text: '{raw_text}'")
            
            if not raw_text.strip():
                return None

            agent = session["agent"]
            history = session["consolidated_text"]
            
            aligned_text = agent.align(history, raw_text)
            logger.info(f"[Stream ASR] Aligned Text: '{aligned_text}'")
            return aligned_text
        except Exception as exc:
            logger.error(f"[Stream ASR] Error in transcription/alignment: {exc}")
            return None
        finally:
            tmp_path.unlink(missing_ok=True)

    aligned = await loop.run_in_executor(None, run_whisper_and_align)

    if aligned is not None:
        with _streaming_sessions_lock:
            if session_id in _streaming_sessions:
                _streaming_sessions[session_id]["consolidated_text"] = aligned
                
        # Emit via Socket.IO directly to the client socket ID
        if socket_id:
            await sio.emit("transcription:stream:interim", {
                "text": aligned,
                "sessionId": session_id
            }, to=socket_id)
        
    return {"status": "processed"}


@app.post("/transcribe/stream/{session_id}/done")
async def receive_stream_done(
    session_id: str,
    prompt_text: str = "",
    keywords: str = "",
    socket_id: str = "",
):
    """POST /transcribe/stream/{session_id}/done — Consolidates the session and returns final clean text."""
    with _streaming_sessions_lock:
        if session_id not in _streaming_sessions:
            raise HTTPException(status_code=404, detail="Streaming session not found or inactive")
        session = _streaming_sessions[session_id]
        if session["status"] == "cancelled":
            return {"status": "cancelled"}

    # Run the final consolidation pass using Llama
    loop = asyncio.get_running_loop()

    def run_final_consolidation():
        try:
            from app.agents import TranscriptionReviewAgent
            reviewer = TranscriptionReviewAgent()
            
            current_text = session["consolidated_text"]
            if not current_text:
                return ""
                
            keywords_list = [k.strip() for k in keywords.split(",") if k.strip()] if keywords else []
            review_result = reviewer.review(
                transcribed_text=current_text,
                keywords=keywords_list,
                prompt_text=prompt_text
            )
            return review_result.corrected_text
        except Exception as exc:
            logger.error(f"[Stream ASR] Error in final consolidation: {exc}")
            return session["consolidated_text"]

    final_text = await loop.run_in_executor(None, run_final_consolidation)
    
    # Emit final consolidated text via Socket.IO
    if socket_id:
        await sio.emit("transcription:stream:final", {
            "text": final_text,
            "sessionId": session_id
        }, to=socket_id)
    
    # Remove session
    with _streaming_sessions_lock:
        _streaming_sessions.pop(session_id, None)
        
    return {"status": "finalized", "text": final_text}


# Allow `python -m app.server` or `uvicorn app.server:app`
if __name__ == "__main__":
    import uvicorn
    print(f"Starting Transcribe Socket.IO server on port {_SERVER_PORT}")
    uvicorn.run("app.server:socket_app", host="127.0.0.1", port=_SERVER_PORT, reload=False)
