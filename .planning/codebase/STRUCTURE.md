# Codebase Structure

**Analysis Date:** 2026-04-14

## Directory Layout

```
transcribe-assistant/
├── app/                      # Python backend
│   ├── ui/                   # (legacy) CustomTkinter UI components
│   ├── ui_flet/              # (legacy) Flet UI components
│   ├── utils/                # Utilities (i18n, clipboard)
│   ├── audio_recorder.py     # sounddevice/soundfile recording
│   ├── transcriber.py        # Transcription routing (Gemini/Whisper)
│   ├── audio_engine.py       # Audio capture subprocess entry point
│   ├── server.py             # FastAPI SSE server
│   ├── config.py             # Environment/configuration loading
│   ├── database.py           # SQLite operations
│   └── network_monitor.py    # Connectivity monitoring
├── electron/                 # Electron + Vue 3 frontend
│   ├── src/
│   │   ├── main/             # Electron main process (TypeScript)
│   │   ├── preload/          # Context bridge (TypeScript)
│   │   └── renderer/         # Vue 3 app
│   │       ├── components/   # Vue components (tabs, editor, bottom bar)
│   │       ├── composables/  # Vue composables (useTranscriptionState, useTabs)
│   │       ├── i18n/         # Internationalization (en.json, pt.json)
│   │       ├── types/        # TypeScript type definitions
│   │       └── App.vue       # Root Vue component
│   ├── package.json          # Node dependencies
│   ├── tsconfig.json         # TypeScript configuration
│   ├── vite.*.config.ts     # Vite configs (main, preload, renderer)
│   └── forge.config.ts       # Electron Forge packaging config
├── .planning/                # GSD planning artifacts
│   ├── codebase/             # Codebase analysis documents
│   ├── phases/               # Phase-by-phase planning
│   └── specs/                # Requirements/specifications
└── pyproject.toml            # Python project configuration (uv)
```

## Directory Purposes

**app/:**
- Purpose: Python backend — transcription, audio, server
- Contains: FastAPI server, transcriber router, audio capture, database, config
- Key files: `server.py`, `transcriber.py`, `audio_engine.py`, `audio_recorder.py`

**electron/src/main/:**
- Purpose: Electron main process — window management, subprocess spawning, IPC
- Key file: `electron/src/main/index.ts`

**electron/src/preload/:**
- Purpose: Secure IPC bridge with context isolation enabled
- Key file: `electron/src/preload/index.ts`

**electron/src/renderer/:**
- Purpose: Vue 3 UI — components, composables, state management
- Key files: `App.vue`, `composables/useTranscriptionState.ts`, `composables/useTabs.ts`

## Key File Locations

**Entry Points:**
- `electron/src/main/index.ts`: Electron app bootstrap
- `electron/src/renderer/main.ts`: Vue app bootstrap
- `app/server.py`: FastAPI server entry (`uv run python -m app.server`)
- `app/audio_engine.py`: Audio subprocess entry (`uv run python app/audio_engine.py`)

**Configuration:**
- `app/config.py`: Environment variable loading (GEMINI_API_KEY, etc.)
- `electron/package.json`: Node dependencies and scripts
- `pyproject.toml`: Python dependencies and uv configuration

**Core Logic:**
- `app/transcriber.py`: Transcription routing (Gemini vs Whisper)
- `app/audio_recorder.py`: Audio capture via sounddevice
- `electron/src/renderer/composables/useTranscriptionState.ts`: Recording state machine

**Testing:**
- Not detected in current structure (no test directories found)

## Naming Conventions

**Files:**
- Python: `snake_case.py`
- TypeScript: `camelCase.ts`, `PascalCase.vue`
- JSON config: `kebab-case.json`

**Directories:**
- Python: `snake_case/`
- TypeScript/Vue: `camelCase/` or `PascalCase/`

**Vue Components:**
- PascalCase `.vue` files with corresponding PascalCase directory
- Example: `RecordButton.vue` in `components/bottom/`

## Where to Add New Code

**New Feature (Python backend):**
- Primary code: `app/` directory
- FastAPI endpoints: `app/server.py`
- Transcription logic: `app/transcriber.py`

**New Vue Component:**
- Implementation: `electron/src/renderer/components/`
- Composables: `electron/src/renderer/composables/`

**New IPC channel:**
- Main process: `electron/src/main/index.ts` (add ipcMain.handle)
- Preload: `electron/src/preload/index.ts` (add to ElectronAPI interface)
- Renderer: `electron/src/renderer/types/global.d.ts`

**Utilities:**
- Shared helpers: `app/utils/`
- Vue composables: `electron/src/renderer/composables/`

## Special Directories

**electron/src/renderer/components/:**
- Purpose: Vue components organized by area (bottom, editor, layout, tabs, topbar)
- Generated: No
- Committed: Yes

**app/agents/:**
- Purpose: (legacy) Agno-based TranscriberAgent — not used in current electron architecture
- Note: Kept for reference; current flow bypasses agent pattern

**.planning/:**
- Purpose: GSD phase planning artifacts
- Generated: Yes (by planning commands)
- Committed: Yes (version controlled)

---

*Structure analysis: 2026-04-14*