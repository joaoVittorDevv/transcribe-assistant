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


def _optional(key: str, default: str) -> str:
    """Return the value of an optional environment variable or a default."""
    value = os.getenv(key, "").strip()
    return value if value else default


# ---------------------------------------------------------------------------
# Dynamic Configuration Values (initialized by load_all_settings)
# ---------------------------------------------------------------------------
GOOGLE_API_KEY: str = ""
GEMINI_MODEL: str = "gemini-2.0-flash"
GEMINI_TIMEOUT: float = 300.0
APP_LANGUAGE: str = "pt"
GROQ_API_KEY: str = ""
GROQ_REVIEW_MODEL: str = "llama-3.1-8b-instant"
WHISPER_MODEL: str = "base"
WHISPER_DEVICE: str = "cpu"
WHISPER_COMPUTE_TYPE: str = "int8"
NETWORK_PING_HOST: str = "8.8.8.8"
NETWORK_PING_PORT: int = 53
NETWORK_CHECK_INTERVAL: int = 10
DATABASE_PATH: Path = _ROOT / _optional("DATABASE_PATH", "transcriber_data.db")
VAULT_PATH: Path = _ROOT / "Vault"
DUAL_INTERMEDIARY_PATH: Path = _ROOT / "DualRecordings"


def load_all_settings() -> None:
    """Load configuration variables from the database, or migrate from .env on first run."""
    global GOOGLE_API_KEY, GEMINI_MODEL, GEMINI_TIMEOUT, APP_LANGUAGE
    global GROQ_API_KEY, GROQ_REVIEW_MODEL, WHISPER_MODEL, WHISPER_DEVICE
    global WHISPER_COMPUTE_TYPE, NETWORK_PING_HOST, NETWORK_PING_PORT
    global NETWORK_CHECK_INTERVAL, VAULT_PATH, DUAL_INTERMEDIARY_PATH

    # Lazy imports to avoid circular dependency with database.py
    import app.database as db
    import app.security as sec

    # Ensure DB schema is up-to-date
    db.initialize_db()

    # Use APP_LANGUAGE existence as indicator that the database has settings configured
    has_db_settings = db.get_setting("APP_LANGUAGE") is not None

    if not has_db_settings:
        # Migrate from .env if present, otherwise use defaults
        env_google = os.getenv("GOOGLE_API_KEY", "").strip()
        env_groq = os.getenv("GROQ_API_KEY", "").strip()

        gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip()
        gemini_timeout = os.getenv("GEMINI_TIMEOUT", "300.0").strip()
        app_lang = os.getenv("APP_LANGUAGE", "pt").strip()
        groq_review = os.getenv("GROQ_REVIEW_MODEL", "llama-3.1-8b-instant").strip()
        whisper_model = os.getenv("WHISPER_MODEL", "base").strip()
        whisper_device = os.getenv("WHISPER_DEVICE", "cpu").strip()
        whisper_comp = os.getenv("WHISPER_COMPUTE_TYPE", "int8").strip()
        net_host = os.getenv("NETWORK_PING_HOST", "8.8.8.8").strip()
        net_port = os.getenv("NETWORK_PING_PORT", "53").strip()
        net_interval = os.getenv("NETWORK_CHECK_INTERVAL", "10").strip()
        vault_path = os.getenv("VAULT_PATH", "Vault").strip()
        dual_path = os.getenv("DUAL_INTERMEDIARY_PATH", "DualRecordings").strip()

        # Encrypt secrets
        enc_google = sec.encrypt_value(env_google) if env_google else ""
        enc_groq = sec.encrypt_value(env_groq) if env_groq else ""

        # Persist configuration in database settings table
        db.set_setting("GOOGLE_API_KEY", enc_google)
        db.set_setting("GROQ_API_KEY", enc_groq)
        db.set_setting("GEMINI_MODEL", gemini_model)
        db.set_setting("GEMINI_TIMEOUT", gemini_timeout)
        db.set_setting("APP_LANGUAGE", app_lang)
        db.set_setting("GROQ_REVIEW_MODEL", groq_review)
        db.set_setting("WHISPER_MODEL", whisper_model)
        db.set_setting("WHISPER_DEVICE", whisper_device)
        db.set_setting("WHISPER_COMPUTE_TYPE", whisper_comp)
        db.set_setting("NETWORK_PING_HOST", net_host)
        db.set_setting("NETWORK_PING_PORT", net_port)
        db.set_setting("NETWORK_CHECK_INTERVAL", net_interval)
        db.set_setting("VAULT_PATH", vault_path)
        db.set_setting("DUAL_INTERMEDIARY_PATH", dual_path)

    # Read active values from DB and apply them to module globals
    enc_google_db = db.get_setting("GOOGLE_API_KEY", "")
    GOOGLE_API_KEY = sec.decrypt_value(enc_google_db) if enc_google_db else ""

    enc_groq_db = db.get_setting("GROQ_API_KEY", "")
    GROQ_API_KEY = sec.decrypt_value(enc_groq_db) if enc_groq_db else ""

    GEMINI_MODEL = db.get_setting("GEMINI_MODEL", "gemini-2.0-flash")
    GEMINI_TIMEOUT = float(db.get_setting("GEMINI_TIMEOUT", "300.0"))
    APP_LANGUAGE = db.get_setting("APP_LANGUAGE", "pt")
    i18n.set("locale", APP_LANGUAGE)

    GROQ_REVIEW_MODEL = db.get_setting("GROQ_REVIEW_MODEL", "llama-3.1-8b-instant")
    WHISPER_MODEL = db.get_setting("WHISPER_MODEL", "base")
    WHISPER_DEVICE = db.get_setting("WHISPER_DEVICE", "cpu")
    WHISPER_COMPUTE_TYPE = db.get_setting("WHISPER_COMPUTE_TYPE", "int8")
    NETWORK_PING_HOST = db.get_setting("NETWORK_PING_HOST", "8.8.8.8")
    NETWORK_PING_PORT = int(db.get_setting("NETWORK_PING_PORT", "53"))
    NETWORK_CHECK_INTERVAL = int(db.get_setting("NETWORK_CHECK_INTERVAL", "10"))
    VAULT_PATH = _ROOT / db.get_setting("VAULT_PATH", "Vault")
    DUAL_INTERMEDIARY_PATH = _ROOT / db.get_setting("DUAL_INTERMEDIARY_PATH", "DualRecordings")


def reload_config() -> None:
    """Reload all settings from the database and propagate changes to other imported modules."""
    import sys
    load_all_settings()

    # Propagate changes to any module that did "from app.config import ..."
    for mod_name, module in list(sys.modules.items()):
        if mod_name.startswith("app.") and module and mod_name != "app.config":
            for var_name in [
                "GOOGLE_API_KEY", "GEMINI_MODEL", "GEMINI_TIMEOUT",
                "GROQ_API_KEY", "GROQ_REVIEW_MODEL", "APP_LANGUAGE",
                "NETWORK_PING_HOST", "NETWORK_PING_PORT", "NETWORK_CHECK_INTERVAL",
                "WHISPER_MODEL", "WHISPER_DEVICE", "WHISPER_COMPUTE_TYPE",
                "VAULT_PATH", "DUAL_INTERMEDIARY_PATH"
            ]:
                if hasattr(module, var_name):
                    setattr(module, var_name, getattr(sys.modules["app.config"], var_name))


# Automatically load configurations at import time
load_all_settings()
