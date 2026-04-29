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


def _on_rms(rms: float) -> None:
    """Called by AudioRecorder on each RMS update — print JSON to stdout."""
    line = json.dumps({"type": "rms", "value": rms})
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def _start(mode: str) -> None:
    global _recorder, _active
    _recorder = AudioRecorder(on_rms_update=_on_rms)
    _recorder.start_recording(source=mode)
    _active = True
    status = {"type": "status", "recording": True, "mode": mode}
    sys.stdout.write(json.dumps(status) + "\n")
    sys.stdout.flush()


def _stop() -> Path | None:
    global _active
    if _recorder is None:
        return None
    try:
        # Save to Vault so audio is persisted even if transcription fails
        wav_path = _recorder.stop_recording(save_dir=VAULT_PATH)
    except Exception:
        wav_path = None
    _active = False
    status = {
        "type": "status",
        "recording": False,
        "wav_path": str(wav_path) if wav_path else None,
    }
    sys.stdout.write(json.dumps(status) + "\n")
    sys.stdout.flush()
    return wav_path


def _cancel() -> None:
    """Stop recording and discard all audio — no WAV file is saved."""
    global _active
    if _recorder is None:
        return
    _recorder.discard_recording()
    _active = False
    status = {
        "type": "status",
        "recording": False,
        "wav_path": None,
    }
    sys.stdout.write(json.dumps(status) + "\n")
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# Command loop
# ---------------------------------------------------------------------------

def _handle_command(cmd: dict) -> None:
    action = cmd.get("action", "")
    if action == "start":
        mode = cmd.get("mode", "mic")
        _start(mode)
    elif action == "stop":
        _stop()
    elif action == "cancel":
        _cancel()
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
