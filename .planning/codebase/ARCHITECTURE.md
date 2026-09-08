# Architecture

**Analysis Date:** 2026-04-14

## Pattern Overview

**Overall:** Multi-process Electron app with Python backend subprocesses

**Key Characteristics:**
- Electron main process spawns two Python subprocesses (server + audio engine)
- Vue 3 renderer communicates with main via contextBridge IPC
- FastAPI SSE server streams transcription to renderer over HTTP
- Audio captured in separate subprocess, WAV path forwarded via IPC

## Layers

**Electron Main Process:**
- Purpose: Application lifecycle, window management, subprocess spawning
- Location: `electron/src/main/index.ts`
- Contains: Window creation, IPC handlers, Python subprocess management
- Depends on: Electron APIs (BrowserWindow, ipcMain, dialog)
- Spawns: `app.server` (FastAPI) and `app/audio_engine.py`

**Electron Preload:**
- Purpose: Secure bridge between main and renderer (context isolation)
- Location: `electron/src/preload/index.ts`
- Exposes: `electronAPI` with audioCommand, onRmsUpdate, onAudioStatus, openFilePicker, readFile

**Vue Renderer:**
- Purpose: UI state management and user interaction
- Location: `electron/src/renderer/`
- Contains: Vue components, composables (useTranscriptionState, useTabs, useEditor)
- Communicates via: window.electronAPI

**Python Server (FastAPI):**
- Purpose: SSE transcription endpoint, session management
- Location: `app/server.py`
- Contains: POST /transcribe (streaming), GET /transcribe/status/{id}, DELETE /transcribe/{id}
- Depends on: `app.transcriber`, `app.network_monitor`, `app.database`

**Python Audio Engine:**
- Purpose: Standalone audio capture subprocess
- Location: `app/audio_engine.py`
- Controlled via: stdin JSON commands (start/stop)
- Emits: stdout JSON lines with RMS values and status events
- Depends on: `app.audio_recorder.AudioRecorder`

**Transcriber:**
- Purpose: AI transcription router (Gemini cloud vs faster-whisper local)
- Location: `app/transcriber.py`
- Modes: auto (fallback), gemini (force cloud), whisper (force local)
- Lazy-loads Whisper model on first use; auto-fallbacks GPU->CPU

## Data Flow

**Recording Flow:**
1. Renderer calls `api.audioCommand({ action: 'start', mode: 'mic' })`
2. Main process forwards to audio engine subprocess via stdin
3. Audio engine starts recording, emits RMS to stdout
4. Main process parses stdout, forwards RMS via `webContents.send('rms-update')`
5. Renderer receives RMS via `onRmsUpdate` callback

**Stop and Transcribe Flow:**
1. Renderer calls `api.audioCommand({ action: 'stop' })`
2. Audio engine writes WAV file, emits status with `wav_path` to stdout
3. Main process forwards via `webContents.send('audio-status', msg)`
4. Renderer receives status, extracts `pendingWavPath`
5. Renderer POSTs WAV path to FastAPI `/transcribe` SSE endpoint
6. SSE stream delivers transcription chunks
7. Renderer accumulates chunks, updates tab content via `updateContent`

## Key Abstractions

**ElectronAPI (preload bridge):**
- Purpose: Type-safe IPC interface exposed to renderer
- File: `electron/src/preload/index.ts`
- Pattern: contextBridge.exposeInMainWorld with typed interface

**TranscriptionState composable:**
- Purpose: Reactive recording/transcription state machine
- Location: `electron/src/renderer/composables/useTranscriptionState.ts`
- States: IDLE | RECORDING | TRANSCRIBING

**Server session registry:**
- Purpose: In-memory session tracking for SSE resume
- Location: `app/server.py` (_active_sessions dict)
- Pattern: Thread-safe with _session_lock

## Entry Points

**Electron Main:**
- Location: `electron/src/main/index.ts`
- Triggers: app.whenReady()
- Responsibilities: Window creation, IPC setup, subprocess spawning

**Python Server:**
- Location: `app/server.py`
- Triggers: `uv run python -m app.server`
- Responsibilities: SSE streaming endpoint on port 18763

**Audio Engine:**
- Location: `app/audio_engine.py`
- Triggers: Spawned by main process
- Responsibilities: Audio capture, RMS calculation, WAV output

**Vue Renderer:**
- Location: `electron/src/renderer/main.ts`
- Triggers: Vite dev server or loaded HTML
- Responsibilities: Vue app bootstrap, component rendering

## Error Handling

**Strategy:** Layer-specific error propagation

**Audio Engine:**
- JSON parse errors on stdout lines: ignored
- Subprocess exit: auto-restart after 500ms if window still open

**FastAPI Server:**
- 100MB file size limit (streaming read)
- Transcription errors: yielded as `[ERROR]` SSE frame
- Session not found: HTTPException 404

**Transcriber:**
- Gemini API errors: raise TranscriptionError (triggers fallback in auto mode)
- Whisper CUDA failures: auto-retry on CPU
- Network offline: raise error in gemini mode, fallback to whisper in auto mode

## Cross-Cutting Concerns

**Logging:** Print statements to stdout/stderr (main process captures Python stdout)
**Validation:** 100MB max file size in server.py; audio format filter in file dialog
**Authentication:** API keys via environment variables (GEMINI_API_KEY, GOOGLE_API_KEY)

---

*Architecture analysis: 2026-04-14*