import re
from pathlib import Path

content = Path("app/server.py").read_text()

# 1. Imports and Socket.IO initialization
new_imports = """from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import socketio

# Default port for the FastAPI server
DEFAULT_PORT = 18763
_SERVER_PORT = int(os.environ.get("TRANSCRIBE_PORT", DEFAULT_PORT))
from pydantic import BaseModel

from app import database as db, network_monitor, transcriber
from app.config import VAULT_PATH

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
"""

content = re.sub(
    r'from pathlib import Path.*?from app\.config import VAULT_PATH',
    new_imports,
    content,
    flags=re.DOTALL
)

# 2. Replace _sse_frame, _transcription_events and _transcription_events_dual
# Instead of replacing, let's find the start of _sse_frame and the end of _transcription_events_dual
start_idx = content.find("def _sse_frame")
# Find the start of Request / Response models
end_idx = content.find("# Request / Response models")

new_tasks = """
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
        preview = chunk_text[:40].replace('\\n', '\\\\n')
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

"""

# find previous newline before _sse_frame
start_idx = content.rfind('\n', 0, start_idx) + 1
content = content[:start_idx] + new_tasks + content[end_idx:]

# 3. Update POST /transcribe
old_transcribe = '''@app.post("/transcribe")
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
    print(f"[SERVER] POST /transcribe recebido | mode={mode} | source={source}")'''
    
new_transcribe = '''@app.post("/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    session_id: Annotated[str | None, Form()] = None,
    prompt_text: Annotated[str, Form()] = "",
    keywords: Annotated[str, Form()] = "",
    mode: Annotated[str, Form()] = "auto",
    source: Annotated[str, Form()] = "mic",
    x_socket_id: str | None = Header(None, alias="X-Socket-ID"),
):
    """POST /transcribe — Accept audio file, stream transcription via Socket.IO."""
    if not x_socket_id:
        raise HTTPException(status_code=400, detail="X-Socket-ID header required")

    print(f"[SERVER] POST /transcribe recebido | mode={mode} | source={source}")'''

content = content.replace(old_transcribe, new_transcribe)

old_transcribe_end = '''    # Wrapper generator that emits initial status events before the main stream
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
    )'''

new_transcribe_end = '''    with _session_lock:
        _active_sessions[sid]["client_sid"] = x_socket_id
        _active_sessions[sid]["seq_counter"] = 0
        _active_sessions[sid]["unacked_buffer"] = []

    # Emit initial status via Socket.IO
    sio.start_background_task(sio.emit, "transcription:status", {"phase": "received", "message": "Áudio recebido, preparando...", "sessionId": sid}, to=x_socket_id)
    sio.start_background_task(sio.emit, "transcription:status", {"phase": "saved", "message": "Arquivo salvo, iniciando processamento...", "sessionId": sid}, to=x_socket_id)

    # Start the actual transcription task in background
    sio.start_background_task(_emit_transcription_task, sid, temp_path, prompt_text, keywords_list, mode, source, x_socket_id)

    return JSONResponse(
        content={"sessionId": sid, "status": "accepted"},
        status_code=202
    )'''

content = content.replace(old_transcribe_end, new_transcribe_end)

# 4. Update POST /transcribe/dual
old_transcribe_dual = '''@app.post("/transcribe/dual")
async def transcribe_dual(
    mic_audio: UploadFile = File(...),
    sys_audio: UploadFile = File(...),
    session_id: Annotated[str | None, Form()] = None,
    prompt_text: Annotated[str, Form()] = "",
    keywords: Annotated[str, Form()] = "",
):
    """POST /transcribe/dual — Accept two audio files for dual mode transcription.

    Streams merged transcription via SSE.
    """'''

new_transcribe_dual = '''@app.post("/transcribe/dual")
async def transcribe_dual(
    mic_audio: UploadFile = File(...),
    sys_audio: UploadFile = File(...),
    session_id: Annotated[str | None, Form()] = None,
    prompt_text: Annotated[str, Form()] = "",
    keywords: Annotated[str, Form()] = "",
    x_socket_id: str | None = Header(None, alias="X-Socket-ID"),
):
    """POST /transcribe/dual — Accept two audio files for dual mode transcription."""
    if not x_socket_id:
        raise HTTPException(status_code=400, detail="X-Socket-ID header required")'''

content = content.replace(old_transcribe_dual, new_transcribe_dual)

old_transcribe_dual_end = '''    logger.info("Starting dual transcription session=%s", sid)

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
    )'''

new_transcribe_dual_end = '''    with _session_lock:
        _active_sessions[sid]["client_sid"] = x_socket_id
        _active_sessions[sid]["seq_counter"] = 0
        _active_sessions[sid]["unacked_buffer"] = []

    logger.info("Starting dual transcription session=%s", sid)

    sio.start_background_task(sio.emit, "transcription:status", {"phase": "received", "message": "Audios dual recebidos...", "sessionId": sid}, to=x_socket_id)
    sio.start_background_task(_emit_transcription_task_dual, sid, mic_path, sys_path, prompt_text, keywords_list, x_socket_id)

    return JSONResponse(
        content={"sessionId": sid, "status": "accepted"},
        status_code=202
    )'''

content = content.replace(old_transcribe_dual_end, new_transcribe_dual_end)

# 5. ASGI Mount & Uvicorn entrypoint
old_mount = '''app = FastAPI(title="Transcribe Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)'''

new_mount = '''app = FastAPI(title="Transcribe Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Wrap the FastAPI app in the Socket.IO ASGI App
socket_app = socketio.ASGIApp(sio, other_app=app)'''

content = content.replace(old_mount, new_mount)

old_main = '''if __name__ == "__main__":
    import uvicorn
    print(f"Starting Transcribe SSE server on port {_SERVER_PORT}")
    uvicorn.run("app.server:app", host="127.0.0.1", port=_SERVER_PORT, reload=False)'''

new_main = '''if __name__ == "__main__":
    import uvicorn
    print(f"Starting Transcribe Socket.IO server on port {_SERVER_PORT}")
    uvicorn.run("app.server:socket_app", host="127.0.0.1", port=_SERVER_PORT, reload=False)'''

content = content.replace(old_main, new_main)

Path("app/server.py").write_text(content)
print("done")
