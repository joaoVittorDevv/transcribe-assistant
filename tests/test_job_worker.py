"""Worker retry/fallback semantics — audio is never lost on provider failure."""

import asyncio
import json
from pathlib import Path

import pytest

from app import database as db
from app.job_worker import TranscriptionJobWorker
from app.transcriber import TranscriptionError


class FakeTranscriber:
    behavior = "ok"

    def __init__(self, is_online_fn):
        pass

    def transcribe(self, audio_path, prompt_text, keywords, mode,
                   on_chunk=None, source="mic", on_status=None):
        if FakeTranscriber.behavior == "504":
            raise TranscriptionError(
                "A conexao expirou (504: DEADLINE_EXCEEDED).",
                provider="google", code="504", retryable=True,
            )
        if FakeTranscriber.behavior == "bad_key":
            raise TranscriptionError(
                "401 unauthorized: API key invalid",
                provider="google", code="401", retryable=False,
            )
        if on_status:
            on_status({"phase": "processing", "message": "..."})
        if on_chunk:
            on_chunk("parcial ")
        return "texto final revisado"


@pytest.fixture()
def worker_env(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.DATABASE_PATH", tmp_path / "w.db")
    monkeypatch.setattr("app.job_worker.transcriber.Transcriber", FakeTranscriber)
    db.initialize_db()
    vault = tmp_path / "recordings" / "pending"
    vault.mkdir(parents=True)
    wav = vault / "rec.wav"
    wav.write_bytes(b"audio")
    events: list[tuple] = []

    async def emit(event, payload):
        events.append((event, payload))

    worker = TranscriptionJobWorker(is_online_fn=lambda: True, emit=emit)
    return worker, wav, events


def _queue_job(wav: Path, mode: str = "gemini") -> str:
    job_id = f"job-{mode}-{wav.stat().st_size}"
    db.create_transcription_job(
        job_id,
        audio_paths=json.dumps([str(wav)]),
        source="mic",
        mode=mode,
    )
    return job_id


async def _drain(worker: TranscriptionJobWorker, runs: int = 1) -> None:
    """Let the worker process up to `runs` job passes."""
    for _ in range(runs):
        job = worker._next_job()
        if job is None:
            return
        await worker._process(job)


def test_success_persists_and_emits(worker_env):
    worker, wav, events = worker_env
    job_id = _queue_job(wav)

    asyncio.run(_drain(worker))

    job = db.get_transcription_job(job_id)
    assert job["status"] == "completed"
    assert job["accumulated_text"] == "texto final revisado"
    kinds = [e for e, _ in events]
    assert "transcription:done" in kinds
    assert wav.exists()


def test_transient_google_error_schedules_retry(worker_env):
    FakeTranscriber.behavior = "504"
    worker, wav, events = worker_env
    job_id = _queue_job(wav)

    asyncio.run(_drain(worker))

    job = db.get_transcription_job(job_id)
    assert job["status"] == "retry_wait"
    assert job["attempts_google"] == 1
    assert job["next_retry_at"] is not None
    assert wav.exists(), "audio must survive a 504"
    status_events = [p for e, p in events if e == "transcription:status"]
    assert any("preservado" in p.get("message", "") for p in status_events)


def test_permanent_google_failure_falls_back_to_groq(worker_env):
    FakeTranscriber.behavior = "bad_key"
    worker, wav, _ = worker_env
    job_id = _queue_job(wav, mode="auto")

    asyncio.run(_drain(worker))  # google attempt fails permanently
    FakeTranscriber.behavior = "ok"

    asyncio.run(_drain(worker))  # groq fallback attempt

    job = db.get_transcription_job(job_id)
    assert job["mode"] == "groq"
    assert job["status"] == "completed"
    assert wav.exists()


def test_cancel_preserves_audio_and_state(worker_env):
    worker, wav, _ = worker_env
    job_id = _queue_job(wav)
    worker.cancel_job(job_id)

    asyncio.run(_drain(worker))

    job = db.get_transcription_job(job_id)
    assert job["status"] == "cancelled"
    assert wav.exists()
