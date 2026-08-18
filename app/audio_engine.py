#!/usr/bin/env python3
"""Standalone crash-safe audio capture subprocess.

Commands arrive as JSON lines on stdin; RMS/status events leave on stdout.
Recordings are written progressively under Vault/recordings/pending.
"""
from __future__ import annotations

import json
import signal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.audio_recorder import AudioRecorder
from app.config import VAULT_PATH

_recorder: AudioRecorder | None = None
_active = False
_dual_mode = False


def _emit(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


def _on_rms(rms: float) -> None:
    _emit({"type": "rms", "value": rms})


def _start(mode: str) -> None:
    global _recorder, _active, _dual_mode
    _dual_mode = mode == "dual"
    _recorder = AudioRecorder(on_rms_update=_on_rms)
    try:
        pending = VAULT_PATH / "recordings" / "pending"
        _recorder.start_recording(source=mode, capture_dir=pending)
        _active = True
        status = {"type": "status", "recording": True, "mode": mode, "dual": _dual_mode}
    except Exception as exc:
        _active = False
        _dual_mode = False
        status = {"type": "status", "recording": False, "dual": False, "error": str(exc)}
    _emit(status)


def _stop() -> tuple[Path, Path] | Path | None:
    global _active, _dual_mode
    if _recorder is None or not _active:
        return None
    try:
        result = _recorder.stop_recording(
            save_dir=VAULT_PATH / "recordings" / "pending"
        )
        error = None
    except Exception as exc:
        result = None
        error = str(exc)
        sys.stderr.write(f"[AudioEngine] Failed to finalize recording: {exc}\n")
        sys.stderr.flush()
    _active = False

    if isinstance(result, tuple):
        mic_path, sys_path = result
        status = {
            "type": "status", "recording": False, "dual": True,
            "mic_wav_path": str(mic_path), "sys_wav_path": str(sys_path),
        }
    else:
        status = {
            "type": "status", "recording": False, "dual": False,
            "wav_path": str(result) if result else None,
        }
    if error:
        status["error"] = error
    _dual_mode = False
    _emit(status)
    return result


def _cancel() -> None:
    """Explicit user discard; unlike provider cancellation this removes audio."""
    global _active, _dual_mode
    if _recorder is not None and _active:
        _recorder.discard_recording()
    _active = False
    _dual_mode = False
    _emit({
        "type": "status", "recording": False, "dual": False,
        "wav_path": None, "mic_wav_path": None, "sys_wav_path": None,
    })


def _handle_command(cmd: dict) -> None:
    action = cmd.get("action", "")
    if action == "start":
        _start(cmd.get("mode", "mic"))
    elif action == "stop":
        _stop()
    elif action == "cancel":
        _cancel()
    else:
        _emit({"type": "error", "message": f"Unknown action: {action}"})


def main() -> None:
    pending = VAULT_PATH / "recordings" / "pending"
    recovered = AudioRecorder.recover_pcm_parts(
        pending,
        logger=lambda message, name: sys.stderr.write(
            f"[AudioEngine] {message % name}\n"
        ),
    )
    if recovered:
        sys.stderr.flush()

    signal.signal(signal.SIGTERM, lambda *_: (_stop(), sys.exit(0)))
    _emit({"type": "ready"})

    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            _handle_command(json.loads(line))
        except json.JSONDecodeError:
            _emit({"type": "error", "message": "Invalid JSON"})

    if _active:
        _stop()


if __name__ == "__main__":
    main()
