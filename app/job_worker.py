"""app.job_worker — Durable background worker for transcription jobs.

Single asyncio task consuming persisted SQLite jobs. Provider failures never
discard audio: the job goes to retry_wait / failed_retryable / failed_permanent
and the WAV stays on disk until retention decides otherwise.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from app import database as db
from app import transcriber

logger = logging.getLogger("app.job_worker")

# Attempt budgets and backoff per provider (phase 4 will tune these).
MAX_ATTEMPTS_GOOGLE = 3
MAX_ATTEMPTS_GROQ = 2
BACKOFF_GOOGLE = [15, 60]
BACKOFF_GROQ = [15]


class TranscriptionJobWorker:
    """Sequential job processor. One job at a time, state in SQLite."""

    def __init__(self, is_online_fn: Callable[[], bool], emit: Callable[..., object]):
        self._is_online = is_online_fn
        self._emit = emit  # async emit(event, payload) — best-effort UI push
        self._task: asyncio.Task | None = None
        self._wake = asyncio.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._cancelled: set[str] = set()

    # -- lifecycle ----------------------------------------------------------

    def start(self) -> None:
        recovered = db.get_recoverable_transcription_jobs()
        if recovered:
            logger.info("[Worker] Recovering %d unfinished job(s)", len(recovered))
        self._loop = asyncio.get_running_loop()
        self._task = asyncio.create_task(self._run(), name="transcription-job-worker")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    def wake(self) -> None:
        """Thread-safe wake (network monitor, HTTP handlers, call_later)."""
        if self._loop is None:
            return
        try:
            self._loop.call_soon_threadsafe(self._wake.set)
        except RuntimeError:
            pass  # loop closed during shutdown

    def cancel_job(self, job_id: str) -> None:
        self._cancelled.add(job_id)
        self._wake.set()

    # -- main loop ----------------------------------------------------------

    async def _run(self) -> None:
        while True:
            job = self._next_job()
            if job is None:
                self._wake.clear()
                await self._wake.wait()
                continue
            await self._process(job)

    def _next_job(self) -> object | None:
        if not self._is_online():
            return None
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")
        for job in db.get_recoverable_transcription_jobs():
            retry_at = job["next_retry_at"]
            if job["status"] != "queued" and (not retry_at or retry_at > now):
                continue
            return job
        return None

    # -- single job ---------------------------------------------------------

    async def _process(self, job) -> None:
        job_id = job["id"]
        import json as _json

        audio_paths = [Path(p) for p in _json.loads(job["audio_paths"])]
        keywords = _json.loads(job["keywords"])
        mode = job["mode"]
        source = job["source"]

        # A job whose audio vanished can never succeed — permanent failure.
        missing = [p for p in audio_paths if not p.exists()]
        if missing:
            db.update_transcription_job(
                job_id,
                status="failed_permanent",
                last_error=f"Audio file(s) missing: {missing}",
            )
            await self._emit(
                "transcription:error",
                {"sessionId": job_id, "message": "Arquivo de áudio não encontrado. Registro preservado."},
            )
            return

        provider = "google" if mode in ("auto", "gemini") else "groq"
        db.update_transcription_job(
            job_id,
            status=f"processing_{provider}",
            provider=provider,
            next_retry_at=None,
        )
        await self._emit(
            "transcription:status",
            {"phase": "processing", "sessionId": job_id,
             "message": "Enviando para transcrição..."},
        )

        accumulated = job["accumulated_text"] or ""
        seq_lock = threading.Lock()
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def chunk_cb(text: str) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, ("CHUNK", text))

        def status_cb(payload: dict) -> None:
            payload["sessionId"] = job_id
            loop.call_soon_threadsafe(queue.put_nowait, ("STATUS", payload))

        def run_provider() -> str:
            t = transcriber.Transcriber(is_online_fn=self._is_online)
            return t.transcribe(
                audio_path=audio_paths if len(audio_paths) > 1 else audio_paths[0],
                prompt_text=job["prompt_text"],
                keywords=keywords,
                mode=mode,
                on_chunk=chunk_cb,
                source=source,
                on_status=status_cb,
            )

        fut = loop.run_in_executor(None, run_provider)
        final_text: str | None = None
        error: Exception | None = None

        while True:
            # Drain queue while the provider thread runs.
            try:
                item = await asyncio.wait_for(queue.get(), timeout=0.25)
            except asyncio.TimeoutError:
                item = None

            if item is not None:
                kind, payload = item
                if kind == "STATUS":
                    await self._emit("transcription:status", payload)
                else:
                    with seq_lock:
                        accumulated += payload
                    # Persist before emit: a UI crash must never lose text.
                    db.update_transcription_job(job_id, accumulated_text=accumulated)
                    await self._emit(
                        "transcription:chunk",
                        {"text": payload, "sessionId": job_id},
                    )

            if fut.done():
                break
            if job_id in self._cancelled:
                break

        if job_id in self._cancelled:
            self._cancelled.discard(job_id)
            fut.cancel()
            db.update_transcription_job(job_id, status="cancelled")
            await self._emit(
                "transcription:status",
                {"phase": "cancelled", "sessionId": job_id, "message": "Cancelado."},
            )
            return

        try:
            final_text = fut.result()
        except Exception as exc:
            error = exc

        if error is not None:
            await self._handle_failure(job, job_id, error)
            return

        db.update_transcription_job(
            job_id,
            status="completed",
            accumulated_text=final_text or accumulated,
            last_error=None,
            next_retry_at=None,
        )
        await self._emit(
            "transcription:status",
            {"phase": "done", "sessionId": job_id, "message": "Transcrição concluída!"},
        )
        await self._emit(
            "transcription:done",
            {"sessionId": job_id, "text": final_text or accumulated},
        )

    async def _handle_failure(self, job, job_id: str, exc: Exception) -> None:
        retryable = _is_retryable(exc)
        attempts_g = int(job["attempts_google"] or 0)
        attempts_q = int(job["attempts_groq"] or 0)
        provider = "google" if job["mode"] in ("auto", "gemini") else "groq"

        if provider == "google":
            attempts_g += 1
            if retryable and attempts_g < MAX_ATTEMPTS_GOOGLE:
                await self._schedule_retry(
                    job_id, "google", attempts_g, attempts_q,
                    BACKOFF_GOOGLE[attempts_g - 1], exc,
                )
                return
            if attempts_q == 0 and job["mode"] == "auto":
                # Auto mode: Google exhausted/errored — retry the whole job via Groq.
                db.update_transcription_job(
                    job_id,
                    attempts_google=attempts_g,
                    mode="groq",
                    status="queued",
                    next_retry_at=None,
                    last_error=str(exc)[:500],
                )
                logger.warning(
                    "[Worker] Google failed after %d attempt(s) — falling back to Groq", attempts_g
                )
                self.wake()
                return
        else:
            attempts_q += 1
            if retryable and attempts_q < MAX_ATTEMPTS_GROQ:
                await self._schedule_retry(
                    job_id, "groq", attempts_g, attempts_q,
                    BACKOFF_GROQ[attempts_q - 1], exc,
                )
                return

        status = "failed_retryable" if retryable else "failed_permanent"
        db.update_transcription_job(
            job_id,
            attempts_google=attempts_g,
            attempts_groq=attempts_q,
            status=status,
            last_error=str(exc)[:500],
        )
        message = (
            "Google/Groq não responderam. O áudio foi preservado e você pode tentar novamente."
            if retryable
            else f"Falha permanente: {exc}"
        )
        await self._emit("transcription:error", {"sessionId": job_id, "message": message})

    async def _schedule_retry(
        self, job_id: str, provider: str,
        attempts_g: int, attempts_q: int, delay_s: int, exc: Exception,
    ) -> None:
        next_at = (datetime.now(timezone.utc) + timedelta(seconds=delay_s)).strftime("%Y-%m-%d %H:%M:%S.%f")
        db.update_transcription_job(
            job_id,
            attempts_google=attempts_g,
            attempts_groq=attempts_q,
            status="retry_wait",
            next_retry_at=next_at,
            last_error=str(exc)[:500],
        )
        logger.warning(
            "[Worker] %s failed (attempt %d) — retry in %ds: %s",
            provider, attempts_g + attempts_q, delay_s, exc,
        )
        await self._emit(
            "transcription:status",
            {"phase": "retry_wait", "sessionId": job_id,
             "message": f"Provedor demorou — nova tentativa em {delay_s}s. Áudio preservado."},
        )
        asyncio.get_running_loop().call_later(delay_s + 1, self.wake)


def _is_retryable(exc: Exception) -> bool:
    explicit = getattr(exc, "retryable", None)
    if explicit is not None:
        return bool(explicit)
    text = str(exc).lower()
    transient = (
        "timeout", "deadline", "504", "502", "503", "500", "429", "overloaded",
        "temporarily", "unavailable", "connection", "offline", "rate limit",
        "reset", "eof", "try again",
    )
    permanent = (
        "api key", "invalid argument", "permission denied", "not found",
        "unauthorized", "forbidden", "audio file", "empty audio",
    )
    if any(k in text for k in permanent):
        return False
    return any(k in text for k in transient)
