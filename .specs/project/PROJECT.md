# Transcribe Assistant

**Vision:** Desktop transcription app with hybrid cloud routing (Gemini ↔ Groq) that runs without local GPU, featuring multi-tab sessions, i18n, and real-time audio metering.
**For:** Professionals and developers who need reliable audio transcription without requiring expensive hardware.
**Solves:** Eliminates GPU dependency for transcription by using cloud APIs with automatic fallback, while providing a clean multi-session tab interface.

## Goals

- Transcribe audio via Google Gemini or Groq Whisper with automatic routing based on connectivity
- Support multiple concurrent recording/transcription sessions via tabs
- Provide real-time audio level feedback during recording
- Validate imported audio files for speech content before transcription
- Persist transcription history, prompts, and keyword glossaries in SQLite

## Tech Stack

**Core:**

- Language: Python 3.12+
- Package Manager: `uv`
- UI Framework: `customtkinter` (CustomTkinter)
- Database: SQLite (`transcriber_data.db`)

**Key dependencies:**

- `google-genai` — Gemini cloud transcription via Files API
- `groq` — Whisper cloud transcription
- `faster-whisper` — Local VAD (Silero VAD) for audio validation (not transcription)
- `sounddevice` + `soundfile` — Audio capture
- `agno` — Agent orchestration (TextReviewerAgent)
- `python-i18n` — Internationalization

## Scope

**v1 includes:**

- Audio recording from microphone or system audio with real-time RMS metering
- Hybrid transcription routing: auto (Groq first → Gemini fallback), force Gemini, force Groq
- TextReviewerAgent for grammar/punctuation correction on Groq transcriptions
- Audio file import with Silero VAD + Gemini validation
- Tab-based multi-session management
- SQLite persistence for sessions, prompts, and keyword glossaries
- Internationalization (Portuguese primary, English)
- Native file dialogs via Zenity on Linux
- Settings modal for prompt/glossary management

**Explicitly out of scope:**

- Local transcription via faster-whisper (VAD only, not transcription)
- Video transcription
- Mobile companion app
- Cloud sync / multi-device
- Flet UI (experimental `app/ui_flet/` not active)

## Constraints

- API keys required: `GOOGLE_API_KEY`, `GROQ_API_KEY`
- Groq free tier: 25 MB audio file limit
- Audio format: 16kHz mono float32 WAV for recording
- Audio validation: Silero VAD via faster-whisper (requires FFmpeg via PyAV)

## Entry Point

```bash
uv run main.py
```

Flow: `main.py` → `app.config` (env validation) → `app.database.initialize_db()` → `app.ui.main_window.MainWindow().mainloop()`
