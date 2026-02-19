"""app.transcriber — AI transcription router (Gemini ↔ Whisper).

Routes audio transcription requests between:
  - Google Gemini (cloud): uploads audio via Files API + System Instruction
  - faster-whisper (local): uses initial_prompt for glossary injection

Modes:
  "auto"    — Try Gemini; fall back to Whisper silently if offline.
  "gemini"  — Force Gemini only; raises TranscriptionError if offline.
  "whisper" — Force Whisper only; loads model lazily (VRAM on demand).

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
    WHISPER_COMPUTE_TYPE,
    WHISPER_DEVICE,
    WHISPER_MODEL,
)

TranscriptionMode = Literal["auto", "gemini", "whisper"]


class TranscriptionError(Exception):
    """Raised when all available transcription backends fail."""


class Transcriber:
    """Routes transcription to Gemini or Whisper based on mode and connectivity.

    Args:
        is_online_fn: Callable that returns True if internet is available.
                      Typically ``network_monitor.is_online``.
    """

    def __init__(self, is_online_fn: callable) -> None:  # type: ignore[valid-type]
        self._is_online_fn = is_online_fn
        self._whisper_model = None  # Lazy-loaded on first use

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
            mode:        Transcription mode — "auto" | "gemini" | "whisper".

        Returns:
            Transcribed text string.

        Raises:
            TranscriptionError: If the selected backend fails and no fallback exists.
        """
        if mode == "whisper":
            # DEBUG - REMOVE LATER
            print("[DEBUG] Transcriber: modo forçado WHISPER")
            return self._transcribe_whisper(audio_path, keywords)

        if mode == "gemini":
            online = self._is_online_fn()
            # DEBUG - REMOVE LATER
            print(f"[DEBUG] Transcriber: modo GEMINI | is_online={online}")
            if not online:
                raise TranscriptionError(
                    "Modo 'Forcar Google' selecionado, mas sem conexao com a internet."
                )
            return self._transcribe_gemini(audio_path, prompt_text, keywords)

        # mode == "auto"
        online = self._is_online_fn()
        # DEBUG - REMOVE LATER
        print(f"[DEBUG] Transcriber: modo AUTO | is_online={online}")
        if online:
            try:
                # DEBUG - REMOVE LATER
                print("[DEBUG] Transcriber: tentando Gemini...")
                result = self._transcribe_gemini(audio_path, prompt_text, keywords)
                # DEBUG - REMOVE LATER
                print("[DEBUG] Transcriber: Gemini OK")
                return result
            except TranscriptionError as exc:
                # DEBUG - REMOVE LATER
                print(
                    f"[DEBUG] Transcriber: Gemini falhou ({exc}), fazendo fallback para Whisper"
                )
        # DEBUG - REMOVE LATER
        print("[DEBUG] Transcriber: usando Whisper local")
        return self._transcribe_whisper(audio_path, keywords)

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
    # Whisper backend
    # ------------------------------------------------------------------

    def _transcribe_whisper(self, audio_path: Path, keywords: list[str]) -> str:
        """Transcribe using faster-whisper with lazy model loading.

        Handles CUDA runtime errors (e.g. libcublas not found) by falling
        back to a CPU-only model on the first inference failure.
        """
        model = self._get_whisper_model()
        initial_prompt = ", ".join(keywords) if keywords else None

        try:
            segments, _ = model.transcribe(
                str(audio_path),
                initial_prompt=initial_prompt,
                language="pt",  # Portuguese — change if needed
                beam_size=5,
                vad_filter=True,  # Remove silence automatically
            )
            return " ".join(seg.text.strip() for seg in segments).strip()
        except Exception as exc:
            err_msg = str(exc)
            # ctranslate2 loads CUDA libs lazily — first .transcribe() may fail
            # even if WhisperModel() succeeded.
            if "lib" in err_msg.lower() and (
                "cuda" in err_msg.lower()
                or "cublas" in err_msg.lower()
                or "cannot be loaded" in err_msg.lower()
            ):
                # DEBUG - REMOVE LATER
                print(
                    f"[DEBUG] Whisper: erro CUDA em runtime ({exc}), recarregando em CPU..."
                )
                self._force_cpu_model()
                try:
                    segments, _ = self._whisper_model.transcribe(
                        str(audio_path),
                        initial_prompt=initial_prompt,
                        language="pt",
                        beam_size=5,
                        vad_filter=True,
                    )
                    # DEBUG - REMOVE LATER
                    print("[DEBUG] Whisper: transcricao em CPU (fallback) OK")
                    return " ".join(seg.text.strip() for seg in segments).strip()
                except Exception as cpu_exc:
                    raise TranscriptionError(
                        f"Whisper falhou em GPU e tambem em CPU: {cpu_exc}"
                    ) from cpu_exc
            raise TranscriptionError(f"Erro na transcricao com Whisper: {exc}") from exc

    def _force_cpu_model(self) -> None:
        """Reload the Whisper model on CPU with int8 (CUDA unavailable fallback)."""
        from faster_whisper import WhisperModel

        self._whisper_model = WhisperModel(
            WHISPER_MODEL, device="cpu", compute_type="int8"
        )
        # DEBUG - REMOVE LATER
        print("[DEBUG] Whisper: modelo recarregado em CPU int8")

    def _get_whisper_model(self):
        """Return the Whisper model, loading it into memory on first call.

        Tries CUDA first; if CUDA libs are missing, falls back to CPU automatically.
        """
        if self._whisper_model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:
                raise TranscriptionError(
                    "faster-whisper nao instalado. Execute: uv add faster-whisper"
                ) from exc

            device = WHISPER_DEVICE
            compute_type = WHISPER_COMPUTE_TYPE

            # DEBUG - REMOVE LATER
            print(
                f"[DEBUG] Whisper: carregando modelo '{WHISPER_MODEL}' | device={device} | compute_type={compute_type}"
            )

            try:
                self._whisper_model = WhisperModel(
                    WHISPER_MODEL,
                    device=device,
                    compute_type=compute_type,
                )
                # DEBUG - REMOVE LATER
                print(f"[DEBUG] Whisper: modelo carregado com sucesso em {device}")
            except Exception as cuda_exc:  # noqa: BLE001
                # CUDA libraries missing or device not available — retry on CPU
                # DEBUG - REMOVE LATER
                print(f"[DEBUG] Whisper: falha ao carregar em {device}: {cuda_exc}")
                print("[DEBUG] Whisper: tentando fallback para CPU...")
                try:
                    self._whisper_model = WhisperModel(
                        WHISPER_MODEL,
                        device="cpu",
                        compute_type="int8",
                    )
                    # DEBUG - REMOVE LATER
                    print("[DEBUG] Whisper: modelo carregado em CPU (fallback)")
                except Exception as cpu_exc:
                    raise TranscriptionError(
                        f"Nao foi possivel carregar o Whisper em GPU nem CPU: {cpu_exc}"
                    ) from cpu_exc

        return self._whisper_model
