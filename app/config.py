"""app.config — Loads and exposes all environment variables.

All application configuration is read from the .env file via python-dotenv.
Use this module as the single source of truth for runtime settings.
"""

from pathlib import Path

from dotenv import load_dotenv
import os

# Load .env from the project root (one level above this file's parent dir)
_ROOT = Path(__file__).parent.parent
load_dotenv(dotenv_path=_ROOT / ".env")


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

# ---------------------------------------------------------------------------
# Whisper (local inference)
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
