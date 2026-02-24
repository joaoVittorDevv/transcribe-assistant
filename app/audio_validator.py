"""app.audio_validator — Speech validation for imported audio files.

Uses a hybrid approach to ensure imported audio contains human speech:
  - Layer 1 (Local): Silero VAD via faster-whisper detects speech ratio
  - Layer 2 (Cloud): Gemini classifies ambiguous cases when online

Thresholds:
  > 40% speech  → Accept (clearly speech)
  15%-40% speech → Gemini validates if online, else accept with warning
  < 15% speech  → Reject (clearly not speech)

Usage:
    validator = AudioValidator(is_online_fn=network_monitor.is_online)
    result = validator.validate(Path("interview.mp3"))
    if result.is_valid:
        transcriber.transcribe(...)
"""

from pathlib import Path
from typing import Literal, NamedTuple

from app.config import GEMINI_MODEL, GOOGLE_API_KEY

# ---------------------------------------------------------------------------
# Supported audio formats
# ---------------------------------------------------------------------------

SUPPORTED_AUDIO_EXTENSIONS: set[str] = {
    ".wav",
    ".mp3",
    ".ogg",
    ".flac",
    ".m4a",
    ".webm",
}

# VAD thresholds
_SPEECH_HIGH_THRESHOLD = 0.40  # Above this: clearly speech
_SPEECH_LOW_THRESHOLD = 0.15  # Below this: clearly not speech
_TARGET_SAMPLE_RATE = 16_000  # VAD requires 16kHz


class ValidationResult(NamedTuple):
    """Result of audio speech validation."""

    is_valid: bool
    confidence: Literal["high", "medium", "low"]
    reason: str


def is_supported_format(path: Path) -> bool:
    """Check if the file extension is in the supported audio formats."""
    return path.suffix.lower() in SUPPORTED_AUDIO_EXTENSIONS


def get_file_dialog_filetypes() -> list[tuple[str, str]]:
    """Return filetypes list for tkinter.filedialog."""
    extensions = " ".join(f"*{ext}" for ext in sorted(SUPPORTED_AUDIO_EXTENSIONS))
    return [
        ("Audio files", extensions),
        ("All files", "*.*"),
    ]


class AudioValidator:
    """Validates whether an audio file contains human speech.

    Args:
        is_online_fn: Callable that returns True if internet is available.
    """

    def __init__(self, is_online_fn: callable) -> None:  # type: ignore[valid-type]
        self._is_online_fn = is_online_fn

    def validate(self, audio_path: Path) -> ValidationResult:
        """Validate if the audio file contains human speech.

        Args:
            audio_path: Path to the audio file.

        Returns:
            ValidationResult with is_valid, confidence, and reason.
        """
        if not audio_path.exists():
            return ValidationResult(False, "high", "Arquivo não encontrado.")

        if not is_supported_format(audio_path):
            return ValidationResult(
                False,
                "high",
                f"Formato não suportado: {audio_path.suffix}",
            )

        try:
            speech_ratio = self._compute_speech_ratio(audio_path)
        except Exception as exc:
            print(f"[DEBUG] AudioValidator: erro ao analisar VAD: {exc}")
            return ValidationResult(False, "low", f"Erro ao analisar o áudio: {exc}")

        print(f"[DEBUG] AudioValidator: speech_ratio={speech_ratio:.2%}")

        if speech_ratio > _SPEECH_HIGH_THRESHOLD:
            return ValidationResult(True, "high", "Fala detectada.")

        if speech_ratio < _SPEECH_LOW_THRESHOLD:
            return ValidationResult(False, "high", "Não parece ser fala humana.")

        # Ambiguous range (15%-40%): try Gemini if online
        if self._is_online_fn():
            return self._classify_with_gemini(audio_path)

        # Offline + ambiguous: accept with warning
        return ValidationResult(
            True,
            "low",
            "Análise inconclusiva (offline). Aceito com ressalva.",
        )

    def _compute_speech_ratio(self, audio_path: Path) -> float:
        """Compute the ratio of speech content using Silero VAD.

        Uses faster-whisper's decode_audio (PyAV/FFmpeg) for robust format
        support — handles MP3, OGG, M4A, etc. without libsndfile limitations.

        Returns:
            Float between 0.0 and 1.0 representing speech proportion.
        """
        from faster_whisper.audio import decode_audio
        from faster_whisper.vad import VadOptions, get_speech_timestamps

        # decode_audio uses PyAV (bundled FFmpeg) and already resamples to 16kHz
        audio = decode_audio(str(audio_path), sampling_rate=_TARGET_SAMPLE_RATE)

        total_samples = len(audio)
        if total_samples == 0:
            return 0.0

        vad_options = VadOptions(
            threshold=0.5,
            min_speech_duration_ms=250,
            min_silence_duration_ms=500,
        )

        timestamps = get_speech_timestamps(
            audio,
            vad_options=vad_options,
            sampling_rate=_TARGET_SAMPLE_RATE,
        )

        speech_samples = sum(ts["end"] - ts["start"] for ts in timestamps)

        return speech_samples / total_samples

    def _classify_with_gemini(self, audio_path: Path) -> ValidationResult:
        """Use Gemini to classify ambiguous audio content."""
        try:
            from google import genai
            from google.genai import types
        except ImportError:
            return ValidationResult(
                True,
                "low",
                "Análise inconclusiva (google-genai indisponível).",
            )

        client = genai.Client(api_key=GOOGLE_API_KEY)

        system_instruction = (
            "Você é um classificador de áudio. "
            "Analise o áudio e determine se o conteúdo principal é fala humana, "
            "música ou ruído/silêncio. "
            "Responda APENAS com uma única palavra: 'fala', 'musica' ou 'ruido'."
        )

        try:
            uploaded_file = client.files.upload(file=str(audio_path))

            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[
                    uploaded_file,
                    "Classifique o conteúdo principal deste áudio.",
                ],
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                ),
            )

            classification = response.text.strip().lower()
            print(f"[DEBUG] AudioValidator Gemini: classificação='{classification}'")

            # Best-effort cleanup
            try:
                client.files.delete(name=uploaded_file.name)
            except Exception:
                pass

            if "fala" in classification:
                return ValidationResult(True, "high", "Gemini confirmou: fala humana.")

            return ValidationResult(
                False,
                "high",
                f"Gemini classificou como: {classification}",
            )

        except Exception as exc:
            print(f"[DEBUG] AudioValidator Gemini error: {exc}")
            # If Gemini fails, accept with low confidence
            return ValidationResult(
                True,
                "low",
                "Análise Gemini falhou. Aceito com ressalva.",
            )
