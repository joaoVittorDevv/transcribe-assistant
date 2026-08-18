"""tests/test_jobs.py — Durable transcription job queue behavior.

Covers the guarantees that matter for data safety:
- accepted jobs are persisted before processing starts
- failed jobs never delete their audio
- retry requeues without touching audio
- cancel preserves audio
- interrupted (processing) jobs are recovered to queued on startup
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import database as db


@pytest.fixture()
def vault(tmp_path, monkeypatch):
    """Isolated Vault so real recordings are never touched."""
    vault = tmp_path / "Vault"
    recordings = vault / "recordings" / "pending"
    recordings.mkdir(parents=True)
    monkeypatch.setattr("app.config.VAULT_PATH", vault)
    monkeypatch.setattr("app.server.VAULT_PATH", vault)
    return recordings


@pytest.fixture()
def job_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test_jobs.db"
    monkeypatch.setattr("app.config.DATABASE_PATH", db_path)
    db.initialize_db()
    return db_path


@pytest.fixture()
def client(job_db):
    from app.server import app
    with TestClient(app) as client:  # runs startup/shutdown events
        yield client


def _make_wav(recordings: Path, name: str = "rec.wav") -> Path:
    import numpy as np
    import soundfile as sf
    p = recordings / name
    sf.write(str(p), np.zeros(16000, dtype=np.float32), 16000)
    return p


def test_queue_job_persists_before_processing(client, vault):
    wav = _make_wav(vault)
    resp = client.post("/transcribe", json={
        "audio_paths": [str(wav)],
        "prompt_text": "ctx",
        "keywords": "a, b",
        "mode": "gemini",
        "source": "mic",
        "socket_id": "sock-1",
    })
    assert resp.status_code == 202
    job_id = resp.json()["sessionId"]

    job = db.get_transcription_job(job_id)
    assert job is not None
    assert job["status"] in ("queued", "processing_google")
    assert json.loads(job["keywords"]) == ["a", "b"]
    assert job["client_sid"] == "sock-1"
    # Audio must still exist — queuing never deletes it.
    assert wav.exists()


def test_failed_job_preserves_audio(client, vault, job_db):
    wav = _make_wav(vault)
    job_id = "job-fail-1"
    db.create_transcription_job(
        job_id,
        audio_paths=json.dumps([str(wav)]),
        source="mic",
        mode="groq",
    )
    db.update_transcription_job(
        job_id,
        status="failed_retryable",
        last_error="504 deadline exceeded",
    )

    resp = client.get(f"/jobs/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "failed_retryable"
    assert wav.exists(), "failed job must never delete its audio"

    # Manual retry requeues and still keeps audio.
    resp = client.post(f"/jobs/{job_id}/retry")
    assert resp.status_code == 200
    assert db.get_transcription_job(job_id)["status"] in ("queued", "processing_groq")
    assert wav.exists()


def test_cancel_job_preserves_audio(client, vault):
    wav = _make_wav(vault)
    job_id = "job-cancel-1"
    db.create_transcription_job(
        job_id,
        audio_paths=json.dumps([str(wav)]),
        source="mic",
        mode="gemini",
    )
    resp = client.post(f"/jobs/{job_id}/cancel")
    assert resp.status_code == 200
    assert db.get_transcription_job(job_id)["status"] == "cancelled"
    assert wav.exists(), "cancel must never delete the recording"


def test_interrupted_jobs_recovered_on_startup(job_db, vault):
    wav = _make_wav(vault)
    db.create_transcription_job(
        "job-crashed",
        audio_paths=json.dumps([str(wav)]),
        source="mic",
        mode="gemini",
    )
    db.update_transcription_job("job-crashed", status="processing_google")

    recovered = db.get_recoverable_transcription_jobs()
    ids = [job["id"] for job in recovered]
    assert "job-crashed" in ids
    assert db.get_transcription_job("job-crashed")["status"] == "queued"


def test_paths_outside_vault_rejected(client, vault, tmp_path):
    rogue = tmp_path / "outside.wav"
    rogue.write_bytes(b"x")
    resp = client.post("/transcribe", json={"audio_paths": [str(rogue)]})
    assert resp.status_code == 400
