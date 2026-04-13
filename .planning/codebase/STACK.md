# Technology Stack

**Analysis Date:** 2026-04-13

## Languages

**Primary:**
- Python 3.12+ - Core application logic, UI, transcription, audio processing

## Runtime

**Environment:**
- Python 3.12 (`.python-version`)
- Package Manager: `uv` with `uv.lock`

**Virtual Environment:**
- `.venv/` directory (PEP 405)

## Frameworks

**UI (Primary):**
- Flet >= 0.82.2 - Primary cross-platform UI framework
- Location: `app/ui_flet/` (main_app.py, tab_manager.py, tab_transcription.py, vu_meter.py, markdown/)

**UI (Legacy):**
- CustomTkinter >= 5.2.2 - Legacy UI framework
- Location: `app/ui/` (main_window.py, prompt_modal.py, sidebar.py, history_window.py)

**Transcription:**
- faster-whisper >= 1.2.1 - Local transcription engine (GPU/CPU)
- google-genai >= 1.64.0 - Cloud transcription via Google Gemini API

**Audio:**
- sounddevice >= 0.5.5 - Audio recording from microphone
- soundfile >= 0.13.1 - Audio file I/O (WAV format)

**AI/Agents:**
- Agno framework - Agent-based transcription orchestration (referenced in memory)
- Note: agents directory exists at `app/agents/` but appears empty

**Markdown:**
- markdown >= 3.10.2 - Markdown parsing and rendering

**Image/Assets:**
- Pillow >= 12.1.1 - Image processing for assets

**Configuration:**
- python-dotenv >= 1.2.1 - Environment variable loading from `.env`

**Internationalization:**
- python-i18n >= 0.3.9 - Multi-language support
- Locale files: `locales/` directory

**Numeric/Array:**
- numpy >= 2.4.2 - Numerical operations (audio processing)

**Electron (Secondary):**
- Electron - Desktop packaging (referenced in `electron/` directory)
- Node.js dependencies in `electron/node_modules/`

## Development Tools

**Formatter:**
- black >= 26.1.0 - Code formatter (line-length: 88, excludes `.agent`, `.venv`, `docs`)

## Key Dependencies (from pyproject.toml)

**Core:**
- `flet>=0.82.2` - UI framework
- `faster-whisper>=1.2.1` - Local transcription
- `google-genai>=1.64.0` - Cloud transcription API
- `sounddevice>=0.5.5` - Audio recording
- `soundfile>=0.13.1` - Audio file handling

**UI/Display:**
- `customtkinter>=5.2.2` - Legacy UI
- `markdown>=3.10.2` - Markdown rendering
- `pillow>=12.1.1` - Image handling

**Support:**
- `numpy>=2.4.2` - Numerical operations
- `python-dotenv>=1.2.1` - Env config
- `python-i18n>=0.3.9` - i18n

## Configuration

**Environment:**
- `.env` file at project root - Contains API keys and runtime settings
- `.env.example` - Template with documented variables

**Key environment variables:**
- `GOOGLE_API_KEY` - Google Gemini API key (required)
- `GEMINI_MODEL` - Model selection (default: gemini-2.0-flash)
- `WHISPER_MODEL` - Local model size (default: base)
- `WHISPER_DEVICE` - cuda or cpu (default: cpu)
- `WHISPER_COMPUTE_TYPE` - float16/int8/float32 (default: int8)
- `DATABASE_PATH` - SQLite database path
- `APP_LANGUAGE` - UI language (default: pt)

## Platform

**Desktop:**
- Electron for desktop application packaging
- Dual UI system: Flet (primary) + CustomTkinter (legacy)

**Database:**
- SQLite (`transcriber_data.db`) - Local persistent storage

---

*Stack analysis: 2026-04-13*
