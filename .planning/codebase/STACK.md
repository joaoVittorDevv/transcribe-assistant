# Technology Stack

**Analysis Date:** 2026-04-14

## Languages

**Primary:**
- Python 3.12+ - Backend, audio processing, transcription, agents
- TypeScript 5.5 - Electron main/preload/renderer process

**Secondary:**
- Vue 3.5 (template) - Electron renderer UI components
- CSS/Tailwind 3.4 - Styling in Electron UI

## Runtime

**Python Environment:**
- Package Manager: `uv` (configured in `pyproject.toml`)
- Lockfile: `uv.lock` present
- Virtual environment: `.venv/` at project root

**Node.js:**
- Electron 32.0 - Desktop shell
- Vite 5.4 - Build tool for renderer process

## Frameworks

**Python Backend:**
- FastAPI 0.115 - SSE server (`app/server.py`)
- sounddevice 0.5.5 + soundfile 0.13.1 - Audio capture and file I/O
- faster-whisper 1.2.1 - Local transcription (GPU/CPU)
- google-genai 1.64.0 - Cloud transcription via Gemini API
- python-dotenv 1.2.1 - Environment variable loading

**Python UI (Legacy):**
- CustomTkinter 5.2.2 - Legacy desktop UI
- flet 0.82.2 - Alternative desktop UI

**Electron UI (Current):**
- electron 32.0 - Desktop application shell
- electron-forge 7.4.0 - Build and packaging
- @vitejs/plugin-vue 5.1.4 - Vue 3 support in Vite
- vue 3.5.12 - UI framework
- quill 2.0.2 - Rich text editor component
- tailwindcss 3.4.13 - CSS framework
- autoprefixer 10.4.20 - CSS vendor prefixes

## Key Dependencies

**Transcription:**
- `faster-whisper>=1.2.1` - Local Whisper inference with VRAM optimization
- `google-genai>=1.64.0` - Gemini API client for cloud transcription

**Audio:**
- `sounddevice>=0.5.5` - PortAudio-based audio input
- `soundfile>=0.13.1` - Audio file reading/writing (WAV format)

**Desktop UI:**
- `flet>=0.82.2` - Cross-platform UI (primary alongside Electron)
- `customtkinter>=5.2.2` - Tkinter-based UI (legacy)

**Server:**
- `fastapi>=0.115.0` - Web framework for SSE backend
- `uvicorn[standard]>=0.34.0` - ASGI server

## Build & Development Tools

**Python:**
- `black>=26.1.0` - Code formatter (line-length: 88)
- `pytest>=8.0` - Testing framework
- `pytest-asyncio>=0.25.0` - Async test support
- `httpx>=0.28.0` - HTTP client for tests

**Electron:**
- `electron-forge` plugins - Vite integration, makers for distribution
- `vue-tsc` - TypeScript type-checking for Vue

## Configuration

**Python Formatter:**
- Tool: `black`
- Config: `pyproject.toml` (line-length: 88)
- Excludes: `.agent`, `.venv`, `docs` directories

**Electron Build:**
- Vite configs: `vite.main.config.ts`, `vite.preload.config.ts`, `vite.renderer.config.ts`
- Forge config: `electron/forge.config.ts`
- Tailwind: `electron/tailwind.config.js`
- PostCSS: `electron/postcss.config.js`
- TypeScript: `electron/tsconfig.json`

**Environment:**
- `.env` at project root - Runtime secrets and config
- `.env.example` - Template with documented variables
- `python-dotenv` for loading environment variables

## Platform Requirements

**Development:**
- Python 3.12+
- Node.js (Electron build)
- `uv` package manager
- PortAudio (system library for sounddevice)

**Production:**
- Electron distributable (Windows/macOS/Linux)
- SQLite database file at `DATABASE_PATH`

---

*Stack analysis: 2026-04-14*
