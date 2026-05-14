"""app.config — Loads and exposes all environment variables.

All application configuration is read from the .env file via python-dotenv.
Use this module as the single source of truth for runtime settings.
"""

import os
import i18n
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the project root (one level above this file's parent dir)
_ROOT = Path(__file__).parent.parent
load_dotenv(dotenv_path=_ROOT / ".env")

# ---------------------------------------------------------------------------
# i18n Initialization
# ---------------------------------------------------------------------------
i18n.load_path.append(str(_ROOT / "locales"))
i18n.set("file_format", "json")
i18n.set("filename_format", "{locale}.{format}")
i18n.set("fallback", "pt")


def _require(key: str) -> str:
    """Return the value of a required environment variable.

    Raises:
        RuntimeError: If the variable is not set or is empty.
    """
    value = os.getenv(key, "").strip()
    if not value:
        raise RuntimeError(
            f"Variavel de ambiente obrigatoria nao configurada: '{key}'\n"
            f"Verifique seu arquivo .env na raiz do projeto."
        )
    return value


def _optional(key: str, default: str) -> str:
    """Return the value of an optional environment variable or a default."""
    value = os.getenv(key, "").strip()
    return value if value else default


# ---------------------------------------------------------------------------
# Google Gemini
# ---------------------------------------------------------------------------
GOOGLE_API_KEY: str = _require("GOOGLE_API_KEY")
GEMINI_MODEL: str = _optional("GEMINI_MODEL", "gemini-2.0-flash")
# Default 300s (5 min) — long audio needs time for upload + streaming.
# Override via .env: GEMINI_TIMEOUT=600
GEMINI_TIMEOUT: float = float(_optional("GEMINI_TIMEOUT", "300.0"))

# ---------------------------------------------------------------------------
# Language
# ---------------------------------------------------------------------------
APP_LANGUAGE: str = _optional("APP_LANGUAGE", "pt")
i18n.set("locale", APP_LANGUAGE)

# ---------------------------------------------------------------------------
# Groq (cloud inference)
# ---------------------------------------------------------------------------
GROQ_API_KEY: str = _require("GROQ_API_KEY")
GROQ_REVIEW_MODEL: str = _optional("GROQ_REVIEW_MODEL", "llama-3.1-8b-instant")

# ---------------------------------------------------------------------------
# Whisper (local inference — kept for AudioValidator VAD)
# ---------------------------------------------------------------------------
WHISPER_MODEL: str = _optional("WHISPER_MODEL", "base")
WHISPER_DEVICE: str = _optional("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE_TYPE: str = _optional("WHISPER_COMPUTE_TYPE", "int8")

# ---------------------------------------------------------------------------
# Network monitor
# ---------------------------------------------------------------------------
NETWORK_PING_HOST: str = _optional("NETWORK_PING_HOST", "8.8.8.8")
NETWORK_PING_PORT: int = int(_optional("NETWORK_PING_PORT", "53"))
NETWORK_CHECK_INTERVAL: int = int(_optional("NETWORK_CHECK_INTERVAL", "10"))

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
DATABASE_PATH: Path = _ROOT / _optional("DATABASE_PATH", "transcriber_data.db")

# ---------------------------------------------------------------------------
# Vault — audio file safe storage
# ---------------------------------------------------------------------------
VAULT_PATH: Path = _ROOT / _optional("VAULT_PATH", "Vault")

# ---------------------------------------------------------------------------
# Dual Recording - Intermediary storage
# ---------------------------------------------------------------------------
# Pasta para áudios do modo dual que falharam na transcrição.
# Os áudios são preservados aqui para debugging.
DUAL_INTERMEDIARY_PATH: Path = _ROOT / _optional("DUAL_INTERMEDIARY_PATH", "DualRecordings")
