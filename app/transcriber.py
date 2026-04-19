"""app.transcriber — AI transcription router (Gemini ↔ Whisper).

Routes audio transcription requests between:
  - Google Gemini (cloud): uploads audio via Files API + System Instruction
  - Groq Whisper (cloud): uses initial_prompt for glossary injection

Modes:
  "auto"    — Try Gemini; fall back to Groq silently if offline.
  "gemini"  — Force Gemini only; raises TranscriptionError if offline.
  "groq"    — Force Groq only; raises TranscriptionError if offline.


Usage:
    transcriber = Transcriber(network_monitor)
    text = transcriber.transcribe(
        audio_path=wav_path,
        prompt_text="Aja como desenvolvedor...",
        keywords=["Reqflow", "faster-whisper"],
        mode="auto",
    )
"""

import os
from pathlib import Path
from typing import Literal

from app.config import (
    GEMINI_MODEL,
    GOOGLE_API_KEY,
    GROQ_API_KEY,
)

TranscriptionMode = Literal["auto", "gemini", "groq"]


class TranscriptionError(Exception):
    """Raised when all available transcription backends fail."""


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
        if mode == "groq":
            online = self._is_online_fn()
            # DEBUG - REMOVE LATER
            print(f"[DEBUG] Transcriber: modo forçado GROQ | is_online={online}")
            if not online:
                raise TranscriptionError(
                    "Modo 'Forçar Groq' selecionado, mas sem conexao com a internet."
                )
            return self._transcribe_groq(audio_path, keywords)

        if mode == "gemini":
            online = self._is_online_fn()
            # DEBUG - REMOVE LATER
            print(f"[DEBUG] Transcriber: modo GEMINI | is_online={online}")
            if not online:
                raise TranscriptionError(
                    "Modo 'Forçar Google' selecionado, mas sem conexao com a internet."
                )
            return self._transcribe_gemini(audio_path, prompt_text, keywords)

        # mode == "auto"
        online = self._is_online_fn()
        # DEBUG - REMOVE LATER
        print(f"[DEBUG] Transcriber: modo AUTO | is_online={online}")
        if not online:
            raise TranscriptionError("Nenhuma engine disponivel (Offline). Tente novamente quando houver internet.")
        
        try:
            # DEBUG - REMOVE LATER
            print("[DEBUG] Transcriber: tentando Groq...")
            result = self._transcribe_groq(audio_path, keywords)
            # DEBUG - REMOVE LATER
            print("[DEBUG] Transcriber: Groq OK")
            return result
        except TranscriptionError as exc:
            # DEBUG - REMOVE LATER
            print(
                f"[DEBUG] Transcriber: Groq falhou ({exc}), fazendo fallback para Gemini"
            )
            
        # DEBUG - REMOVE LATER
        print("[DEBUG] Transcriber: usando Gemini (fallback)")
        return self._transcribe_gemini(audio_path, prompt_text, keywords)

    # ------------------------------------------------------------------
    # Gemini backend
    # ------------------------------------------------------------------

    def _transcribe_gemini(
        self, audio_path: Path, prompt_text: str, keywords: list[str]
    ) -> str:
        """Upload audio to Gemini Files API and request transcription."""
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

        # Upload the audio file to Files API (SDK >= 1.0 uses file=, not path=)
        try:
            uploaded_file = client.files.upload(file=str(audio_path))
            # DEBUG - REMOVE LATER
            print(f"[DEBUG] Gemini: upload concluido -> {uploaded_file.name}")
        except Exception as exc:
            raise TranscriptionError(f"Falha ao fazer upload do audio: {exc}") from exc

        try:
            # SDK >= 1.0 simplified API: pass file object + string directly.
            # The SDK auto-converts to the correct Part/Content types internally.
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[uploaded_file, "Transcreva o audio acima com precisao."],
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                ),
            )
            # DEBUG - REMOVE LATER
            print(f"[DEBUG] Gemini: resposta recebida ({len(response.text)} chars)")
        except Exception as exc:
            raise TranscriptionError(f"Erro na requisicao ao Gemini: {exc}") from exc
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

    def _transcribe_groq(self, audio_path: Path, keywords: list[str]) -> str:
        """Transcribe using Groq API whisper-large-v3-turbo.
        """
        try:
            from groq import Groq
        except ImportError as exc:
            raise TranscriptionError(
                "groq nao instalado. Execute: uv add groq"
            ) from exc

        # LIMIT LIMIT: Groq free tier limit is 25MB
        if audio_path.stat().st_size > 25 * 1024 * 1024:
            raise TranscriptionError("Arquivo de áudio muito grande para a API do Groq (> 25MB).")

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
                    temperature=0.0
                )
            return str(transcription).strip()
        except Exception as exc:
            raise TranscriptionError(f"Erro na transcricao com Groq: {exc}") from exc

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
