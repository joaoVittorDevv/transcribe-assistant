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
from fastapi.responses import JSONResponse, StreamingResponse
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
    cors_allowed_origins='*',
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
        vault_root=VAULT_PATH,
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
    minimax_key_configured: bool
    minimax_key_masked: str
    minimax_base_url: str
    minimax_model: str
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
    minimax_key: str | None = None
    minimax_base_url: str | None = None
    minimax_model: str | None = None
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
    minimax_key: str | None = None
    minimax_base_url: str | None = None


class FetchModelsResponse(PydanticBaseModel):
    gemini_models: list[str]
    groq_models: list[str]
    minimax_models: list[str]


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
        minimax_key_configured=bool(config.MINIMAX_API_KEY),
        minimax_key_masked=_get_masked_key(config.MINIMAX_API_KEY),
        minimax_base_url=config.MINIMAX_BASE_URL,
        minimax_model=config.MINIMAX_MODEL,
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

    # 5. MiniMax Key & Config
    if body.minimax_key is not None:
        mmkey = body.minimax_key.strip()
        if "..." in mmkey or "********" in mmkey or (len(mmkey) > 0 and mmkey.endswith("XXXX")):
            pass
        elif mmkey == "":
            db.set_setting("MINIMAX_API_KEY", "")
        else:
            db.set_setting("MINIMAX_API_KEY", sec.encrypt_value(mmkey))

    if body.minimax_base_url is not None:
        db.set_setting("MINIMAX_BASE_URL", body.minimax_base_url.strip())

    if body.minimax_model is not None:
        db.set_setting("MINIMAX_MODEL", body.minimax_model.strip())

    # 6. Language
    if body.app_language is not None:
        db.set_setting("APP_LANGUAGE", body.app_language.strip())

    # 7. Paths
    if body.vault_path is not None:
        db.set_setting("VAULT_PATH", body.vault_path.strip())
    if body.dual_intermediary_path is not None:
        db.set_setting("DUAL_INTERMEDIARY_PATH", body.dual_intermediary_path.strip())

    # 8. Network
    if body.network_ping_host is not None:
        db.set_setting("NETWORK_PING_HOST", body.network_ping_host.strip())
    if body.network_ping_port is not None:
        db.set_setting("NETWORK_PING_PORT", str(body.network_ping_port))
    if body.network_check_interval is not None:
        db.set_setting("NETWORK_CHECK_INTERVAL", str(body.network_check_interval))

    # 9. Tray & Alerts
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
    """POST /settings/models — Dynamically fetch models available for Gemini, Groq and MiniMax."""
    import app.config as config
    from app.models_fetcher import fetch_gemini_models, fetch_groq_models, fetch_minimax_models

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

    # Determine MiniMax Key & Base URL
    minimax_key = body.minimax_key
    if minimax_key is not None:
        minimax_key = minimax_key.strip()
        if "..." in minimax_key or "********" in minimax_key or minimax_key == "":
            minimax_key = config.MINIMAX_API_KEY
    else:
        minimax_key = config.MINIMAX_API_KEY

    minimax_base_url = body.minimax_base_url or config.MINIMAX_BASE_URL

    # Fetch models
    gemini_list = fetch_gemini_models(gemini_key)
    groq_list = fetch_groq_models(groq_key)
    minimax_list = fetch_minimax_models(minimax_key, base_url=minimax_base_url)

    return FetchModelsResponse(
        gemini_models=gemini_list,
        groq_models=groq_list,
        minimax_models=minimax_list
    )


# ---------------------------------------------------------------------------
# Rewrite Agents API & Meta-Agent Endpoints
# ---------------------------------------------------------------------------

class CreateAgentWithAIRequest(PydanticBaseModel):
    user_intent: str
    target_provider: str | None = "minimax"


class RewriteAgentPayload(PydanticBaseModel):
    name: str
    slug: str
    icon: str = "✨"
    description: str = ""
    system_prompt: str
    tone: str = "balanced"
    target_audience: str = "general"
    remove_filler_words: bool = True
    preserve_slang: bool = False
    prefix_template: str = ""
    suffix_template: str = ""
    output_format: str = "markdown"
    provider: str = "minimax"
    model: str = "MiniMax-M2.7-highspeed"
    temperature: float = 0.3
    is_default: bool = False
    agent_type: str = "no-check"


class RewriteRequest(PydanticBaseModel):
    agent_id: int
    text: str


@app.get("/agents")
async def list_agents():
    """GET /agents — List all configured rewrite agents."""
    agents = db.list_rewrite_agents()
    return [dict(a) for a in agents]


@app.get("/agents/{agent_id}")
async def get_agent(agent_id: int):
    """GET /agents/{agent_id} — Get single rewrite agent by id."""
    agent = db.get_rewrite_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    return dict(agent)


@app.post("/agents")
async def create_agent(payload: RewriteAgentPayload):
    """POST /agents — Create a new rewrite agent."""
    try:
        new_id = db.create_rewrite_agent(
            name=payload.name,
            slug=payload.slug,
            icon=payload.icon,
            description=payload.description,
            system_prompt=payload.system_prompt,
            tone=payload.tone,
            target_audience=payload.target_audience,
            remove_filler_words=payload.remove_filler_words,
            preserve_slang=payload.preserve_slang,
            prefix_template=payload.prefix_template,
            suffix_template=payload.suffix_template,
            output_format=payload.output_format,
            provider=payload.provider,
            model=payload.model,
            temperature=payload.temperature,
            is_default=payload.is_default,
            agent_type=payload.agent_type,
        )
        return {"ok": True, "id": new_id, "message": "Agente criado com sucesso"}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail=f"Já existe um agente com o slug '{payload.slug}'")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/agents/{agent_id}")
async def update_agent(agent_id: int, payload: RewriteAgentPayload):
    """PUT /agents/{agent_id} — Update an existing rewrite agent."""
    existing = db.get_rewrite_agent(agent_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    db.update_rewrite_agent(agent_id, **payload.model_dump())
    return {"ok": True, "message": "Agente atualizado com sucesso"}


@app.delete("/agents/{agent_id}")
async def delete_agent(agent_id: int):
    """DELETE /agents/{agent_id} — Delete a rewrite agent."""
    existing = db.get_rewrite_agent(agent_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    db.delete_rewrite_agent(agent_id)
    return {"ok": True, "message": "Agente removido com sucesso"}


@app.post("/agents/{agent_id}/set-default")
async def set_default_agent(agent_id: int):
    """POST /agents/{agent_id}/set-default — Mark agent as default."""
    existing = db.get_rewrite_agent(agent_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    db.set_default_rewrite_agent(agent_id)
    return {"ok": True, "message": "Agente definido como padrão"}


class BuilderStartRequest(PydanticBaseModel):
    session_id: str
    model: str | None = None
    initial_agent: dict | None = None


class BuilderChatRequest(PydanticBaseModel):
    session_id: str
    message: str
    model: str | None = None


class BuilderResetRequest(PydanticBaseModel):
    session_id: str


class RewriteRequest(PydanticBaseModel):
    agent_id: int
    text: str
    model: str | None = None


@app.post("/agents/builder/start")
async def builder_start_endpoint(body: BuilderStartRequest):
    """POST /agents/builder/start — Initialize an ephemeral Agno Meta-Architect session."""
    from app.agents_service import start_builder_session
    try:
        data = start_builder_session(
            session_id=body.session_id,
            model_name=body.model or "",
            initial_agent=body.initial_agent,
        )
        return {"ok": True, **data}
    except Exception as e:
        logger.error("Error starting builder session: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/agents/builder/chat")
async def builder_chat_endpoint(body: BuilderChatRequest):
    """POST /agents/builder/chat — Send turn to the conversational Agno Meta-Architect."""
    from app.agents_service import chat_builder_session
    try:
        data = chat_builder_session(
            session_id=body.session_id,
            user_message=body.message,
            model_name=body.model or "",
        )
        return {"ok": True, **data}
    except Exception as e:
        logger.error("Error in builder chat: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/agents/builder/reset")
async def builder_reset_endpoint(body: BuilderResetRequest):
    """POST /agents/builder/reset — Completely purge memory of the builder session."""
    from app.agents_service import reset_builder_session
    try:
        reset_builder_session(session_id=body.session_id)
        return {"ok": True, "message": "Memória da sessão de construção expurgada com sucesso."}
    except Exception as e:
        logger.error("Error resetting builder session: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/agents/rewrite")
async def rewrite_text_endpoint(body: RewriteRequest):
    """POST /agents/rewrite — Execute text rewriting using Agno."""
    from app.agents_service import execute_rewrite_agno
    try:
        result = execute_rewrite_agno(
            agent_id=body.agent_id,
            text=body.text,
            model_override=body.model or "",
        )
        return {"ok": True, **result}
    except Exception as e:
        logger.error("Error executing rewrite: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/agents/rewrite/stream")
async def rewrite_text_stream_endpoint(body: RewriteRequest):
    """POST /agents/rewrite/stream — Stream text rewriting and reasoning events via SSE."""
    from app.agents_service import execute_rewrite_stream_agno
    import json

    def event_generator():
        try:
            for event in execute_rewrite_stream_agno(
                agent_id=body.agent_id,
                text=body.text,
                model_override=body.model or "",
            ):
                yield f"data: {json.dumps(event)}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            logger.error("Error during rewrite stream: %s", e)
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


class RewriteFeedbackRequest(PydanticBaseModel):
    agent_id: int
    original_text: str
    current_draft: str
    feedback: str
    model: str | None = None


@app.post("/agents/rewrite/feedback/stream")
async def rewrite_feedback_stream_endpoint(body: RewriteFeedbackRequest):
    """POST /agents/rewrite/feedback/stream — Stream iterative refinement on draft via SSE."""
    from app.agents_service import execute_rewrite_feedback_stream
    import json

    def event_generator():
        try:
            for event in execute_rewrite_feedback_stream(
                agent_id=body.agent_id,
                original_text=body.original_text,
                current_draft=body.current_draft,
                feedback=body.feedback,
                model_override=body.model or "",
            ):
                yield f"data: {json.dumps(event)}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            logger.error("Error during rewrite feedback stream: %s", e)
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# Allow `python -m app.server` or `uvicorn app.server:app`
if __name__ == "__main__":
    import uvicorn
    print(f"Starting Transcribe Socket.IO server on port {_SERVER_PORT}")
    uvicorn.run("app.server:socket_app", host="127.0.0.1", port=_SERVER_PORT, reload=False)
