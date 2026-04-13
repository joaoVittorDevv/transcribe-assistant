# External Integrations

**Analysis Date:** 2026-04-13

## APIs & External Services

**Transcription - Cloud:**
- Google Gemini API - Cloud-based audio transcription
  - SDK: `google-genai>=1.64.0`
  - Auth: `GOOGLE_API_KEY` environment variable
  - Endpoint: Google AI Studio (https://aistudio.google.com/app/apikey)
  - Model: Configurable via `GEMINI_MODEL` (default: gemini-2.0-flash)
  - Features: Audio file upload, streaming responses, system instruction injection
  - Timeout: Configurable via `GEMINI_TIMEOUT` (default: 60s)

**Transcription - Local:**
- faster-whisper - Local neural transcription (no external API)
  - Model sizes: tiny | base | small | medium | large-v3
  - Device: CUDA (GPU) or CPU fallback
  - Compute types: float16 (GPU), int8 (low VRAM), float32 (CPU)

## Data Storage

**Database:**
- SQLite - Local file-based database
  - Location: `transcriber_data.db` (or custom path via `DATABASE_PATH`)
  - Client: Native Python sqlite3
  - Purpose: Transcription history, sessions, prompts

**File Storage:**
- Local filesystem only - Audio files saved locally
- Audio format: WAV (via sounddevice + soundfile)

## Authentication & Identity

**API Authentication:**
- Google Gemini API key-based authentication
  - Env var: `GOOGLE_API_KEY`
  - Managed via: `python-dotenv` loading from `.env`

## Network Dependencies

**Internet Connectivity:**
- Required for: Google Gemini cloud transcription
- Optional for: faster-whisper local transcription (works offline)
- Monitoring: `NetworkMonitor` class pings `NETWORK_PING_HOST:NETWORK_PING_PORT` (default: 8.8.8.8:53)
- Check interval: Configurable via `NETWORK_CHECK_INTERVAL` (default: 10s)

**Network Checks:**
- Used by: Transcriber to determine auto/gemini mode routing
- Auto mode: Falls back to local Whisper when offline

## CI/CD & Deployment

**Desktop Packaging:**
- Electron - Desktop application bundling
  - Directory: `electron/`
  - Dependencies: `electron/node_modules/`

**Package Manager:**
- uv - Python package management
  - Lockfile: `uv.lock`

## Environment Configuration

**Required env vars:**
- `GOOGLE_API_KEY` - Google Gemini API key (required for cloud transcription)

**Optional env vars:**
- `GEMINI_MODEL` - Model name (default: gemini-2.0-flash)
- `GEMINI_TIMEOUT` - API timeout in seconds (default: 60.0)
- `WHISPER_MODEL` - Local model size (default: base)
- `WHISPER_DEVICE` - cuda or cpu (default: cpu)
- `WHISPER_COMPUTE_TYPE` - float16, int8, or float32 (default: int8)
- `NETWORK_PING_HOST` - Connectivity check host (default: 8.8.8.8)
- `NETWORK_PING_PORT` - Connectivity check port (default: 53)
- `NETWORK_CHECK_INTERVAL` - Seconds between checks (default: 10)
- `DATABASE_PATH` - SQLite file path
- `APP_LANGUAGE` - UI language code (default: pt)

**Secrets location:**
- `.env` file at project root (NOT committed to git)

## Internal Module Dependencies

**Config Module:**
- `app/config.py` - Single source of truth for environment variables
- Loads `.env` via `python-dotenv`
- Validates required vars on import

**Key modules:**
- `app/transcriber.py` - Routes between Gemini/Whisper based on connectivity
- `app/audio_recorder.py` - Audio capture via sounddevice
- `app/database.py` - SQLite operations
- `app/network_monitor.py` - Internet connectivity monitoring

## Webhooks & Callbacks

**Internal callbacks:**
- `on_chunk` callback in Transcriber - Streams transcription chunks to UI
- Network monitor callback system for connectivity changes

---

*Integration audit: 2026-04-13*
