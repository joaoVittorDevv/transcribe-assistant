# External Integrations

**Analysis Date:** 2026-04-14

## APIs & External Services

**Cloud Transcription:**
- Google Gemini API - Primary cloud transcription backend
  - SDK: `google-genai>=1.64.0`
  - Auth: `GOOGLE_API_KEY` environment variable
  - Model: Configurable via `GEMINI_MODEL` (default: `gemini-2.0-flash`)
  - Features: Files API upload, streaming responses, system instruction injection
  - Timeout: Configurable via `GEMINI_TIMEOUT` (default: 60s)

**Local Transcription:**
- faster-whisper - Local Whisper inference
  - Model: Configurable via `WHISPER_MODEL` (default: `base`)
  - Device: `WHISPER_DEVICE` (`cuda` or `cpu`)
  - Compute type: `WHISPER_COMPUTE_TYPE` (`float16`, `int8`, `float32`)
  - Fallback: Automatic CPU fallback if CUDA libraries unavailable

**Network Monitoring:**
- Connectivity check via DNS ping to `NETWORK_PING_HOST:NETWORK_PING_PORT`
  - Default: `8.8.8.8:53` (Google DNS)
  - Interval: Configurable via `NETWORK_CHECK_INTERVAL` (default: 10s)
  - Used by: `app/network_monitor.py` to determine online/offline status

## Data Storage

**SQLite Database:**
- Engine: Python `sqlite3` (standard library)
- Location: `DATABASE_PATH` env var (default: `transcriber_data.db` at project root)
- Schema: Defined in `app/database.py`
- Purpose: Session storage, transcription history

## Audio Hardware Integration

**Audio Capture:**
- Library: `sounddevice` (PortAudio bindings)
- Recording modes: `mic` (microphone), `system` (system audio)
- Implementation: `app/audio_recorder.py`
- Subprocess: `app/audio_engine.py` runs as standalone process

**Audio File I/O:**
- Library: `soundfile`
- Format: WAV
- Purpose: Recording output, transcription input

**RMS Monitoring:**
- Real-time audio level streaming via subprocess IPC
- JSON messages on stdout: `{"type": "rms", "value": <float>}`
- Forwarded from audio_engine to renderer via Electron IPC

## IPC Between Processes (Electron)

**Architecture:**
- Main process (`electron/src/main/index.ts`) - Orchestrates subprocesses
- Preload script (`electron/src/preload/index.ts`) - Secure IPC bridge
- Renderer process - Vue 3 UI components

**Subprocesses Managed by Main:**
1. **FastAPI SSE Server** - `uv run python -m app.server`
   - Communicates via stdio
   - Handles SSE transcription streaming

2. **Audio Engine** - `uv run python app/audio_engine.py`
   - Controlled via stdin JSON commands
   - Emits JSON lines to stdout (RMS updates, status)
   - Auto-restarts after exit if window still open

**IPC Channels:**
- `audio-command` - Send commands to audio_engine (start/stop)
- `rms-update` - Real-time audio level from audio_engine to renderer
- `audio-status` - Recording state and wav_path on stop
- `open-file-dialog` - Native file picker for audio files
- `read-file` - Read file contents for transcription

**Preload API** (`window.electronAPI`):
```typescript
audioCommand(cmd: { action: string; mode?: string }): void
onRmsUpdate(callback: (value: number) => void): () => void
onAudioStatus(callback: (status: AudioStatus) => void): () => void
openFilePicker(accept: string[]): Promise<string | null>
readFile(path: string): Promise<ArrayBuffer | null>
```

## Authentication & Identity

**API Key Management:**
- `GOOGLE_API_KEY` - Gemini API key (required)
- Stored in `.env` at project root
- Loaded via `python-dotenv` in `app/config.py`

## Monitoring & Observability

**Error Tracking:**
- Debug prints to stderr/stdout in development
- No external error tracking service configured

**Logging:**
- Python: print statements to stdout/stderr
- Electron main: `[sse-server]` and `[audio-engine]` prefixed output
- Renderer: Browser console

## CI/CD & Deployment

**Electron Distribution:**
- electron-forge with makers for deb, rpm, squirrel, zip
- Build commands: `npm run package`, `npm run make`

**Python Backend:**
- Packaged with Electron as subprocesses
- Uses `uv` for dependency resolution

## Environment Configuration

**Required env vars:**
- `GOOGLE_API_KEY` - Gemini API authentication
- `GEMINI_MODEL` - Model identifier (optional, has default)
- `WHISPER_MODEL` - Local model size (optional, has default)
- `WHISPER_DEVICE` - cuda/cpu (optional, has default)
- `WHISPER_COMPUTE_TYPE` - Precision type (optional, has default)
- `DATABASE_PATH` - SQLite file location (optional, has default)

**Secrets location:**
- `.env` file at project root (NOT committed to git)

---

*Integration audit: 2026-04-14*
