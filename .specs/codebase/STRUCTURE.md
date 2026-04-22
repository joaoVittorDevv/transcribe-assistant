# Project Structure

**Root:** `/home/jao/VSCode/transcribe-assistant/`

## Directory Tree

```
transcribe-assistant/
├── .claude/                   # Claude Code config + specs
│   ├── settings.local.json
│   └── worktrees/
├── .specs/                    # Spec-driven documentation
│   ├── project/
│   │   ├── PROJECT.md
│   │   ├── ROADMAP.md
│   │   └── STATE.md
│   ├── codebase/
│   │   ├── STACK.md
│   │   ├── ARCHITECTURE.md
│   │   ├── CONVENTIONS.md
│   │   ├── STRUCTURE.md
│   │   ├── TESTING.md
│   │   ├── INTEGRATIONS.md
│   │   └── CONCERNS.md
│   └── features/
├── app/                       # Main application package
│   ├── __init__.py            # Package marker (empty)
│   ├── config.py              # Environment variables + i18n init
│   ├── database.py            # SQLite CRUD layer
│   ├── transcriber.py         # Transcription routing (Gemini ↔ Groq)
│   ├── audio_recorder.py      # Audio capture with RMS metering
│   ├── audio_validator.py     # Audio validation (Silero VAD + Gemini)
│   ├── network_monitor.py     # TCP connectivity monitor
│   ├── agents/
│   │   ├── __init__.py
│   │   └── text_reviewer_agent.py  # Groq grammar/punctuation reviewer
│   └── ui/
│       ├── __init__.py
│       ├── main_window.py     # Main application window (CTk)
│       ├── vu_meter.py       # VU meter widget (LED-style bar)
│       ├── sidebar.py         # (legacy — not used in current UI)
│       ├── prompt_modal.py    # Settings modal (prompt + glossary editor)
│       ├── history_window.py  # Session history browser
│       └── native_dialog.py   # File picker (Zenity on Linux)
├── assets/                    # Icons and images
├── docs/                      # Planning documents (PLAN-*.md)
├── locales/                   # i18n JSON files (pt.json, en.json)
├── tests/                     # Test files (currently empty)
├── electron/                  # Electron UI scaffold (Vue 3, NOT ACTIVE)
├── main.py                    # Entry point
├── pyproject.toml            # Dependencies + black config
├── .env.example              # Environment template
└── uv.lock                    # Locked dependencies
```

## Module Organization

### Core Application (`app/`)

| Module | Purpose |
|--------|---------|
| `config.py` | Env vars + i18n init, validates `GOOGLE_API_KEY`, `GROQ_API_KEY` |
| `database.py` | SQLite persistence (sessions, prompts, keywords) |
| `transcriber.py` | AI routing, Gemini/Groq API calls, title generation |
| `audio_recorder.py` | Sounddevice audio capture, RMS computation |
| `audio_validator.py` | Silero VAD + Gemini audio validation |
| `network_monitor.py` | TCP connectivity checker (daemon thread) |
| `agents/text_reviewer_agent.py` | Groq-based grammar/punctuation correction |

### UI Components (`app/ui/`)

| File | Purpose |
|------|---------|
| `main_window.py` | Main `CTk` window — all recording/transcription orchestration |
| `vu_meter.py` | Animated vertical VU meter (green → yellow → red) |
| `prompt_modal.py` | Settings `CTkToplevel` — prompt name, text, glossary editor |
| `history_window.py` | Session history `CTkToplevel` — browse/restore/copy sessions |
| `native_dialog.py` | File picker — Zenity on Linux, tkinter fallback |
| `sidebar.py` | Legacy — prompt selector sidebar (NOT used in current UI) |

## Where Things Live

**Audio Recording:**

- Logic: `app/audio_recorder.py` → `AudioRecorder` class
- Source selection: `microphone` or `system_audio` via `set_source()`
- Device resolution: `_resolve_device()` handles PipeWire/PulseAudio/ALSA
- UI feedback: `app/ui/vu_meter.py` → `VUMeter.set_level()`

**Audio Validation:**

- Logic: `app/audio_validator.py` → `AudioValidator` class
- Silero VAD: `faster_whisper.vad.get_speech_timestamps()`
- Gemini fallback: for ambiguous 15-40% speech ratio
- Config: `SUPPORTED_AUDIO_EXTENSIONS` set

**Transcription:**

- Routing: `app/transcriber.py` → `Transcriber` class
- Modes: `auto` (Groq → Gemini fallback), `gemini` (force), `groq` (force)
- Agents: `app/agents/text_reviewer_agent.py` → `TextReviewerAgent`

**Persistence:**

- CRUD: `app/database.py` — functions for sessions, prompts, keywords
- Schema: auto-created via `initialize_db()` with migration try/except
- Auto-save: debounced 1s after text changes via `after()`

**UI Layout:**

- Window: `app/ui/main_window.py` → `MainWindow(ctk.CTk)`
- Tab bar: horizontal scrollable frame with `+` button
- Text area: `CTkTextbox` per tab
- Controls: timer, VU meter, source selector, action buttons

## Special Directories

| Directory | Purpose |
|-----------|---------|
| `.specs/` | Spec-driven development documentation |
| `.claude/` | Claude Code configuration |
| `electron/` | Electron/Vue 3 UI scaffold (paused, not active) |
| `locales/` | i18n JSON translation files |
| `docs/` | Feature planning documents (PLAN-*.md) |
| `vault/` | (not analyzed) |
| `recovery/` | (not analyzed) |
| `app/ui_flet/` | Experimental Flet UI (archived, not loaded) |

## Obsolete / Archived

| Path | Status |
|------|--------|
| `app/ui/sidebar.py` | Exists but not integrated in current `main_window.py` |
| `app/ui_flet/` | Experimental Flet UI — not loaded by `main.py` |
| `electron/` | Vue 3 Electron scaffold — `feat/electron-interface` branch |
| `app/agents/transcriber_agent.py` | Mentioned in docs but file may not exist |
