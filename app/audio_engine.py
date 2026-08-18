#!/usr/bin/env python3
"""app/audio_engine.py — Standalone subprocess for audio capture.

Controlled via stdin JSON commands. Emits RMS and status events to stdout as JSON lines.

Usage:
    python app/audio_engine.py
Commands (stdin):
    {"action": "start", "mode": "mic"}
    {"action": "start", "mode": "system"}
    {"action": "stop"}
    {"action": "cancel"}
"""
from __future__ import annotations

import json
import signal
import sys
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

# Ensure project root on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.audio_recorder import AudioRecorder
from app.config import VAULT_PATH

# ---------------------------------------------------------------------------
# Recorder + event emitter
# ---------------------------------------------------------------------------

_recorder: AudioRecorder | None = None
_active = False
_dual_mode = False
_streaming_thread: threading.Thread | None = None
_stop_streaming_event: threading.Event | None = None


def _on_rms(rms: float) -> None:
    """Called by AudioRecorder on each RMS update — print JSON to stdout."""
    line = json.dumps({"type": "rms", "value": rms})
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def _streaming_loop(session_id: str, socket_id: str, prompt: str, keywords: str) -> None:
    """Background thread that captures recent audio frames and HTTP POSTs them to the server."""
    from app.utils.audio_stream_processor import AudioStreamProcessor

    # Initial buffer sleep to gather some audio
    time.sleep(1.5)

    while _stop_streaming_event and not _stop_streaming_event.is_set():
        start_time = time.time()
        try:
            if _recorder is None or not _active:
                break

            # 1. Fetch recent frames
            if _dual_mode:
                mic_audio, sys_audio = _recorder.get_recent_dual_frames(duration_sec=3.0)
                audio_data = AudioStreamProcessor.mix_dual_audio(mic_audio, sys_audio)
            else:
                audio_data = _recorder.get_recent_frames(duration_sec=3.0)

            # 2. Encode to WAV and POST to local FastAPI server
            if len(audio_data) > 0:
                wav_io = AudioStreamProcessor.to_wav_bytes(audio_data)
                wav_bytes = wav_io.getvalue()

                query_params = urllib.parse.urlencode({
                    "prompt_text": prompt,
                    "keywords": keywords,
                    "socket_id": socket_id,
                })
                url = f"http://localhost:18763/transcribe/stream/{session_id}/chunk?{query_params}"

                req = urllib.request.Request(
                    url=url,
                    data=wav_bytes,
                    headers={"Content-Type": "audio/wav"},
                )
                with urllib.request.urlopen(req, timeout=5) as response:
                    response.read()

        except Exception as exc:
            sys.stderr.write(f"[Streaming Loop Error] {exc}\n")
            sys.stderr.flush()

        # Enforce 1.5s interval
        elapsed = time.time() - start_time
        sleep_time = max(0.1, 1.5 - elapsed)
        if _stop_streaming_event and _stop_streaming_event.wait(timeout=sleep_time):
            break


def _start(
    mode: str,
    is_streaming: bool = False,
    session_id: str = "",
    socket_id: str = "",
    prompt: str = "",
    keywords: str = "",
) -> None:
    global _recorder, _active, _dual_mode, _stop_streaming_event, _streaming_thread
    _dual_mode = mode == "dual"
    _recorder = AudioRecorder(on_rms_update=_on_rms)
    try:
        _recorder.start_recording(source=mode)
        _active = True
        status = {"type": "status", "recording": True, "mode": mode, "dual": _dual_mode}
        
        # Start streaming thread if requested
        if is_streaming and session_id:
            _stop_streaming_event = threading.Event()
            _streaming_thread = threading.Thread(
                target=_streaming_loop,
                args=(session_id, socket_id, prompt, keywords),
                daemon=True,
                name="ASRStreamingThread",
            )
            _streaming_thread.start()
            logger_info = f"[AudioEngine] Streaming session started: {session_id}"
            sys.stderr.write(logger_info + "\n")
            sys.stderr.flush()

    except Exception as exc:
        _active = False
        _dual_mode = False
        status = {"type": "status", "recording": False, "dual": False, "error": str(exc)}
    sys.stdout.write(json.dumps(status) + "\n")
    sys.stdout.flush()


def _stop(session_id: str = "", socket_id: str = "", prompt: str = "", keywords: str = "") -> tuple[Path, Path] | Path | None:
    global _active, _dual_mode, _stop_streaming_event, _streaming_thread
    if _stop_streaming_event:
        _stop_streaming_event.set()
        _stop_streaming_event = None
        _streaming_thread = None

    if _recorder is None:
        return None
    try:
        # Recordings are durable source data, never disposable request files.
        recordings_dir = VAULT_PATH / "recordings" / "pending"
        result = _recorder.stop_recording(save_dir=recordings_dir)
    except Exception as exc:
        sys.stderr.write(f"[AudioEngine] Failed to save recording: {exc}\n")
        sys.stderr.flush()
        result = None
    _active = False

    # Send final done trigger if this was a streaming session
    if session_id:
        try:
            query_params = urllib.parse.urlencode({
                "prompt_text": prompt,
                "keywords": keywords,
                "socket_id": socket_id,
            })
            url = f"http://localhost:18763/transcribe/stream/{session_id}/done?{query_params}"
            req = urllib.request.Request(url=url, data=b"") # Empty POST
            with urllib.request.urlopen(req, timeout=10) as response:
                response.read()
        except Exception as exc:
            sys.stderr.write(f"[Streaming Done Error] {exc}\n")
            sys.stderr.flush()

    if isinstance(result, tuple):
        # Dual mode: return both paths
        mic_path, sys_path = result
        _dual_mode = False
        status = {
            "type": "status",
            "recording": False,
            "dual": True,
            "mic_wav_path": str(mic_path) if mic_path else None,
            "sys_wav_path": str(sys_path) if sys_path else None,
        }
    else:
        # Single mode (mic/system): return single path
        wav_path = result
        _dual_mode = False
        status = {
            "type": "status",
            "recording": False,
            "dual": False,
            "wav_path": str(wav_path) if wav_path else None,
        }

    sys.stdout.write(json.dumps(status) + "\n")
    sys.stdout.flush()
    return result


def _cancel() -> None:
    """Stop recording and discard all audio — no WAV file is saved."""
    global _active, _dual_mode, _stop_streaming_event, _streaming_thread
    if _stop_streaming_event:
        _stop_streaming_event.set()
        _stop_streaming_event = None
        _streaming_thread = None

    if _recorder is None:
        return
    _recorder.discard_recording()
    _active = False
    _dual_mode = False
    status = {
        "type": "status",
        "recording": False,
        "dual": False,
        "wav_path": None,
        "mic_wav_path": None,
        "sys_wav_path": None,
    }
    sys.stdout.write(json.dumps(status) + "\n")
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# Command loop
# ---------------------------------------------------------------------------

_current_session_id = ""
_current_socket_id = ""
_current_prompt = ""
_current_keywords = ""

def _handle_command(cmd: dict) -> None:
    global _current_session_id, _current_socket_id, _current_prompt, _current_keywords
    action = cmd.get("action", "")
    if action == "start":
        mode = cmd.get("mode", "mic")
        is_streaming = cmd.get("isStreaming", False)
        _current_session_id = cmd.get("sessionId", "")
        _current_socket_id = cmd.get("socketId", "")
        _current_prompt = cmd.get("prompt", "")
        _current_keywords = cmd.get("keywords", "")
        _start(mode, is_streaming, _current_session_id, _current_socket_id, _current_prompt, _current_keywords)
    elif action == "stop":
        _stop(_current_session_id, _current_socket_id, _current_prompt, _current_keywords)
        _current_session_id = ""
        _current_socket_id = ""
        _current_prompt = ""
        _current_keywords = ""
    elif action == "cancel":
        _cancel()
        _current_session_id = ""
        _current_socket_id = ""
        _current_prompt = ""
        _current_keywords = ""
    else:
        err = {"type": "error", "message": f"Unknown action: {action}"}
        sys.stdout.write(json.dumps(err) + "\n")
        sys.stdout.flush()


def main() -> None:
    global _recorder
    signal.signal(signal.SIGTERM, lambda *_: (_stop(), sys.exit(0)))

    # Bug 1b fix: emit ready signal so main process knows engine is alive
    ready = {"type": "ready"}
    sys.stdout.write(json.dumps(ready) + "\n")
    sys.stdout.flush()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            cmd = json.loads(line)
        except json.JSONDecodeError:
            err = {"type": "error", "message": "Invalid JSON"}
            sys.stdout.write(json.dumps(err) + "\n")
            sys.stdout.flush()
            continue
        _handle_command(cmd)

    # Graceful EOF — stop if still recording
    if _active:
        _stop()
    sys.exit(0)


if __name__ == "__main__":
    main()
