"""Conservative recording retention — only terminal, expired files are removed."""

import asyncio
import os
import time
from pathlib import Path

from app.job_worker import TranscriptionJobWorker


def _worker(root: Path) -> TranscriptionJobWorker:
    async def emit(*args):
        pass
    return TranscriptionJobWorker(lambda: True, emit, vault_root=root)


def test_retention_removes_only_expired_terminal_audio(tmp_path: Path):
    recordings = tmp_path / "recordings"
    files = {}
    for sub in ("pending", "failed", "completed", "cancelled"):
        folder = recordings / sub
        folder.mkdir(parents=True)
        files[sub] = folder / f"{sub}.wav"
        files[sub].write_bytes(b"audio")
        old = time.time() - 10 * 86400
        os.utime(files[sub], (old, old))

    _worker(tmp_path).run_retention_sweep()

    assert files["pending"].exists(), "pending recordings never auto-delete"
    assert files["failed"].exists(), "failed recordings never auto-delete"
    assert not files["completed"].exists()
    assert not files["cancelled"].exists()


def test_recent_terminal_audio_is_kept(tmp_path: Path):
    for sub in ("completed", "cancelled"):
        folder = tmp_path / "recordings" / sub
        folder.mkdir(parents=True)
        (folder / "recent.wav").write_bytes(b"audio")

    _worker(tmp_path).run_retention_sweep()

    assert (tmp_path / "recordings" / "completed" / "recent.wav").exists()
    assert (tmp_path / "recordings" / "cancelled" / "recent.wav").exists()
