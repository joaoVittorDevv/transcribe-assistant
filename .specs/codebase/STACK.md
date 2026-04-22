# Tech Stack

**Analyzed:** 2026-04-21

## Core

- Language: Python 3.12+
- Runtime: CPython
- Package Manager: `uv`
- Formatter: `black` (line-length: 88, excludes `.agent`, `.venv`, `docs`)

## UI

- Framework: `customtkinter` (≥5.2.2) — CustomTkinter-based desktop UI
- Theme: Dark mode (`ctk.set_appearance_mode("dark")`)
- Layout: Single-window with horizontal tab bar + text area + controls

## Audio

- `sounddevice` (≥0.5.5) — Microphone/system audio capture
- `soundfile` (≥0.13.1) — WAV file I/O
- `numpy` (≥2.4.2) — RMS computation for VU meter
- `faster-whisper` (≥1.2.1) — Silero VAD for audio validation (NOT local transcription)

## Transcription

- `google-genai` (≥1.64.0) — Gemini cloud transcription via Files API
- `groq` (≥1.1.2) — Whisper cloud transcription
- `agno` — Agent orchestration with streaming (TextReviewerAgent)

## Data

- `sqlite3` — Built-in, via `app/database.py`
- Database file: `transcriber_data.db` (configurable via `DATABASE_PATH`)

## i18n

- `python-i18n` (≥0.3.9) — Locale files in `locales/`

## Images

- `pillow` (≥12.1.1) — Icon resizing for window taskbar icon

## External Services

- Google Gemini API — Cloud transcription
- Groq API — Whisper cloud transcription + TextReviewerAgent
- Network: TCP connection to `NETWORK_PING_HOST` (default 8.8.8.8:53)

## Development

- Testing: `pytest` (in `tests/` — currently empty)
- Formatter: `black` ≥26.1.0
- No type checker currently enforced (type annotations present but unchecked)
