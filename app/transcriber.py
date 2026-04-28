"""app.transcriber — AI transcription router (Gemini ↔ Whisper).

Routes audio transcription requests between:
  - Google Gemini (cloud): uploads audio via Files API + System Instruction
  - Groq Whisper (cloud): uses initial_prompt for glossary injection

When using Groq, transcribed text is automatically reviewed by the Groq
TranscriptionReviewAgent (``llama-3.1-8b-instant``) for grammar and punctuation
correction and keyword near-match flagging.

Audio files longer than 10 minutes are automatically routed to Google Gemini
for transcription, regardless of the selected mode — Groq does not accept long
audio and client-side chunking degrades transcription quality.

Modes:
  "auto"    — Try Groq + review; fall back to Gemini silently.
  "gemini"  — Force Gemini only; raises TranscriptionError if offline.
  "groq"    — Force Groq only; raises TranscriptionError if offline.
             Audio >10 min is automatically redirected to Gemini.


Usage:
    transcriber = Transcriber(network_monitor)
    text = transcriber.transcribe(
        audio_path=wav_path,
        prompt_text="Aja como desenvolvedor...",
        keywords=["Reqflow", "faster-whisper"],
        mode="auto",
    )
"""

from __future__ import annotations

import os
import queue
from pathlib import Path
from typing import Literal

from app.audio_chunker import AudioChunkingError, split_audio
from app.config import (
    GEMINI_MODEL,
    GOOGLE_API_KEY,
    GROQ_API_KEY,
)

TranscriptionMode = Literal["auto", "gemini", "groq"]


class TranscriptionError(Exception):
    """Raised when all available transcription backends fail."""


# Module-level UI queue imported from app.ui.main_window for progress updates
_ui_queue: queue.Queue | None = None


def _get_ui_queue() -> queue.Queue:
    global _ui_queue
    if _ui_queue is None:
        # Try to import from main_window (avoids circular import at module level)
        try:
            from app.ui import main_window as mw

            _ui_queue = mw._ui_queue
        except Exception:
            # Fallback: create a dummy queue if import fails
            _ui_queue = queue.Queue()
    return _ui_queue


def _put_progress(message: str) -> None:
    """Send a transcription_progress event to the UI queue if available."""
    try:
        q = _get_ui_queue()
        q.put(("transcription_progress", message))
    except Exception:
        pass


class Transcriber:
    """Routes transcription to Gemini or Groq based on mode and connectivity.

    Args:
        is_online_fn: Callable that returns True if internet is available.
                      Typically ``network_monitor.is_online``.
    """

    def __init__(self, is_online_fn: callable) -> None:  # type: ignore[valid-type]
        self._is_online_fn = is_online_fn

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def _is_long_audio(audio_path: Path, max_duration_sec: float = 600.0) -> bool:
        """Check if audio file exceeds max_duration_sec (default 10 minutes).

        Returns False if the file cannot be read — lets the backend handle errors.
        """
        try:
            import soundfile as sf

            info = sf.info(str(audio_path))
            return info.duration > max_duration_sec
        except Exception:
            return False

    def transcribe(
        self,
        audio_path: Path,
        prompt_text: str,
        keywords: list[str],
        mode: TranscriptionMode = "auto",
    ) -> str:
        """Transcribe an audio file and return the resulting text.

        Args:
            audio_path:  Path to the WAV file to transcribe.
            prompt_text: The active prompt's instruction text (used by Gemini).
            keywords:    Glossary words (used by both backends differently).
            mode:        Transcription mode — "auto" | "gemini" | "groq".

        Returns:
            Transcribed text string.

        Raises:
            TranscriptionError: If the selected backend fails and no fallback exists.
        """
        online = self._is_online_fn()
        if not online:
            raise TranscriptionError(
                "Nenhuma engine disponivel (Offline). Tente novamente quando houver internet."
            )

        # Áudios com mais de 10 minutos são sempre enviados ao Google Gemini,
        # independentemente do modo selecionado — o Groq não aceita arquivos
        # longos e o chunking degrada a qualidade da transcrição.
        if self._is_long_audio(audio_path):
            _put_progress(
                "Áudio longo detectado (>10 min). Enviando diretamente para "
                "o Google Gemini para transcrição completa..."
            )
            print(
                f"[DEBUG] Transcriber: áudio longo (>10 min), redirecionando "
                f"para Gemini (modo={mode})"
            )
            return self._transcribe_gemini(audio_path, prompt_text, keywords)

        if mode == "groq":
            print(f"[DEBUG] Transcriber: modo forçado GROQ | is_online={online}")
            return self._transcribe_groq(audio_path, keywords, prompt_text)

        if mode == "gemini":
            print(f"[DEBUG] Transcriber: modo GEMINI | is_online={online}")
            return self._transcribe_gemini(audio_path, prompt_text, keywords)

        # mode == "auto"
        print(f"[DEBUG] Transcriber: modo AUTO | is_online={online}")
        try:
            print("[DEBUG] Transcriber: tentando Groq...")
            result = self._transcribe_groq(audio_path, keywords, prompt_text)
            print("[DEBUG] Transcriber: Groq OK")
            return result
        except TranscriptionError as exc:
            print(
                f"[DEBUG] Transcriber: Groq falhou ({exc}), fazendo fallback para Gemini"
            )

        print("[DEBUG] Transcriber: usando Gemini (fallback)")
        return self._transcribe_gemini(audio_path, prompt_text, keywords)

    # ------------------------------------------------------------------
    # Gemini backend
    # ------------------------------------------------------------------

    def _transcribe_gemini(
        self, audio_path: Path, prompt_text: str, keywords: list[str]
    ) -> str:
        """Upload audio to Gemini Files API and request transcription.

        Gemini handles long audio files natively via its Files API — no
        client-side chunking needed. The 10+ minute redirect is handled at
        the ``transcribe()`` routing layer.
        """
        return self._transcribe_gemini_single(audio_path, prompt_text, keywords)

    def _transcribe_gemini_single(
        self, audio_path: Path, prompt_text: str, keywords: list[str]
    ) -> str:
        """Transcribe a single audio file via Gemini Files API (no chunking)."""
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise TranscriptionError(
                "google-genai nao instalado. Execute: uv add google-genai"
            ) from exc

        client = genai.Client(api_key=GOOGLE_API_KEY)

        # Build system instruction combining prompt text and glossary
        system_instruction = self._build_system_instruction(prompt_text, keywords)

        # Upload the audio file to Files API
        try:
            uploaded_file = client.files.upload(file=str(audio_path))
            print(f"[DEBUG] Gemini: upload concluido -> {uploaded_file.name}")
        except Exception as exc:
            raise TranscriptionError(
                f"Falha ao fazer upload do audio: {exc}"
            ) from exc

        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[uploaded_file, "Transcreva o audio acima com precisao."],
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                ),
            )
            print(
                f"[DEBUG] Gemini: resposta recebida ({len(response.text)} chars)"
            )
        except Exception as exc:
            raise TranscriptionError(
                f"Erro na requisicao ao Gemini: {exc}"
            ) from exc
        finally:
            # Best-effort cleanup of the uploaded file
            try:
                client.files.delete(name=uploaded_file.name)
            except Exception:
                pass

        return response.text.strip()

    @staticmethod
    def _build_system_instruction(prompt_text: str, keywords: list[str]) -> str:
        """Combine prompt text and glossary into a Gemini system instruction."""
        parts = []
        if prompt_text:
            parts.append(prompt_text)
        if keywords:
            glossary_line = (
                "Glossario de termos especificos que podem aparecer na transcricao "
                f"(use a grafia correta): {', '.join(keywords)}."
            )
            parts.append(glossary_line)
        parts.append("Produza apenas o texto transcrito, sem comentarios adicionais.")
        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Groq backend
    # ------------------------------------------------------------------

    def _transcribe_groq(
        self, audio_path: Path, keywords: list[str], prompt_text: str
    ) -> str:
        """Transcribe using Groq Whisper.

        Only called for files <= 10 minutes (longer audio is redirected to
        Gemini at the ``transcribe()`` routing layer). Files exceeding 25 MB
        are split into chunks via ``split_audio`` and transcribed sequentially.
        """
        try:
            import soundfile as sf
        except ImportError as exc:
            raise TranscriptionError(
                "soundfile nao instalado. Execute: uv add soundfile"
            ) from exc

        # Check if chunking is needed
        audio_size_mb = audio_path.stat().st_size / (1024 * 1024)
        try:
            info = sf.info(str(audio_path))
            total_duration = info.duration
        except Exception as exc:
            raise TranscriptionError(
                f"Nao foi possível ler duracao do audio: {exc}"
            ) from exc

        max_duration_sec = 600.0  # 10 minutes default
        needs_chunking = audio_size_mb > 25.0 or total_duration > max_duration_sec

        if not needs_chunking:
            # Short file — transcribe directly without chunking
            return self._transcribe_groq_single(audio_path, keywords, prompt_text)

        # Long file — use chunking
        texts: list[str] = []
        try:
            with split_audio(audio_path, max_duration_sec=max_duration_sec) as chunks:
                total_chunks = len(chunks)
                for k, (chunk_path, _chunk_dur) in enumerate(chunks, start=1):
                    _put_progress(f"Transcribing chunk {k}/{total_chunks}...")
                    # Per-chunk 25 MB validation is done inside split_audio
                    text = self._transcribe_groq_single(
                        chunk_path, keywords, prompt_text
                    )
                    texts.append(text)
        except AudioChunkingError as exc:
            raise TranscriptionError(
                f"Chunking falhou: {exc}"
            ) from exc

        return "\n\n".join(texts)

    def _transcribe_groq_single(
        self, audio_path: Path, keywords: list[str], prompt_text: str
    ) -> str:
        """Transcribe a single audio file with Groq Whisper (no chunking)."""
        try:
            from groq import Groq
        except ImportError as exc:
            raise TranscriptionError(
                "groq nao instalado. Execute: uv add groq"
            ) from exc

        # Validate size for single chunk (should already be ≤25MB from chunker)
        if audio_path.stat().st_size > 25 * 1024 * 1024:
            raise TranscriptionError(
                "Chunk muito grande para a API do Groq (> 25MB)."
            )

        client = Groq(api_key=GROQ_API_KEY)
        initial_prompt = ", ".join(keywords) if keywords else ""

        try:
            with open(audio_path, "rb") as file:
                transcription = client.audio.transcriptions.create(
                    file=file,
                    model="whisper-large-v3-turbo",
                    prompt=initial_prompt,
                    response_format="text",
                    language="pt",
                    temperature=0.0,
                )
            raw_text = str(transcription).strip()
        except Exception as exc:
            raise TranscriptionError(
                f"Erro na transcricao com Groq: {exc}"
            ) from exc

        # --- Review step: grammar / punctuation correction ---
        print("[DEBUG] Groq: chamando TranscriptionReviewAgent...")
        try:
            from app import database as db

            default = db.get_default_prompt()
            keywords_from_db = (
                [row["palavra"] for row in db.get_keywords_by_prompt(default["id"])]
                if default
                else []
            )
            prompt_text_from_db = default["texto_prompt"] if default else ""
        except Exception as exc:
            print(
                f"[DEBUG] Groq: failed to fetch default prompt ({exc}), "
                "using empty values"
            )
            keywords_from_db = []
            prompt_text_from_db = ""

        try:
            from app.agents import TranscriptionReviewAgent

            reviewer = TranscriptionReviewAgent()
            review_result = reviewer.review(
                transcribed_text=raw_text,
                keywords=keywords_from_db,
                prompt_text=prompt_text_from_db,
            )

            print(
                f"[DEBUG] Groq review: changes={review_result.has_changes}, "
                f"near_matches={review_result.near_matches}"
            )
            if review_result.diff_lines:
                print("[DEBUG] Groq diff:\n" + "\n".join(review_result.diff_lines))

            return review_result.corrected_text
        except Exception as exc:
            # Graceful degradation: if review fails, return raw transcription
            print(f"[DEBUG] Groq review failed ({exc}), usando texto bruto.")
            return raw_text

    # ------------------------------------------------------------------
    # Title Generation
    # ------------------------------------------------------------------

    def generate_title(self, text: str) -> str:
        """Generate a short title (max 5 words) for a given text using Gemini."""
        if not self._is_online_fn():
            return "Nova Sessão"

        try:
            from google import genai
            from google.genai import types
        except ImportError:
            return "Nova Sessão"

        client = genai.Client(api_key=GOOGLE_API_KEY)

        system_instruction = "Você é um assistente especialista em sumarização. Crie um título descritivo para este texto usando no máximo 5 palavras. Produza apenas o título e nada mais. Não use aspas."

        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[text],
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                ),
            )
            return response.text.strip()
        except Exception as exc:
            print(f"[DEBUG] Gemeni title generation failed: {exc}")
            return "Nova Sessão"
