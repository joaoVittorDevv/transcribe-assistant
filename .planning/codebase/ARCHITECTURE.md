# Architecture

**Analysis Date:** 2026-04-13

## Pattern Overview

**Overall:** Layered desktop application with a service-oriented backend and dual UI frontends (legacy CustomTkinter + active Flet).

**Key Characteristics:**
- Strict startup validation: `app.config` is imported before any UI is constructed; a missing required env var aborts with a non-zero exit code.
- Backend services are framework-agnostic: `AudioRecorder`, `Transcriber`, and `NetworkMonitor` carry no UI imports.
- Transcription is dispatched in a background `threading.Thread` so the UI thread remains responsive.
- Gemini streaming is exposed via an `on_chunk` callback, letting the UI receive incremental text without polling.

## Layers

**Configuration:**
- Purpose: Load `.env`, validate required keys, expose typed constants, initialize i18n locale.
- Location: `app/config.py`
- Depends on: `python-dotenv`, `i18n` library
- Used by: every other module that needs a setting

**Core Services (Backend):**
- Purpose: Audio capture, transcription routing, network polling — all UI-independent.
- Location: `app/audio_recorder.py`, `app/transcriber.py`, `app/network_monitor.py`, `app/audio_validator.py`
- Depends on: `app/config.py`, `sounddevice`, `soundfile`, `numpy`, `faster-whisper`, `google-genai`
- Used by: UI layer (both Flet and CustomTkinter)

**Persistence:**
- Purpose: SQLite CRUD for prompts, glossary keywords, and transcription sessions.
- Location: `app/database.py`
- Depends on: `app/config.py` (for `DATABASE_PATH`)
- Used by: UI layer (Sidebar loads prompts; history windows query sessions)

**UI — Flet (primary):**
- Purpose: Active production UI built with the Flet framework.
- Location: `app/ui_flet/`
- Depends on: all core services, `app/database.py`, `flet`
- Entry point: `main_flet.py` → `app/ui_flet/main_app.py::init_app(page)`

**UI — CustomTkinter (legacy):**
- Purpose: Original desktop UI, kept for reference during migration.
- Location: `app/ui/`
- Entry point: `main.py` → `app/ui/main_window.py::MainWindow`

**Utilities:**
- Purpose: Shared helpers not tied to a specific layer.
- Location: `app/utils/`
- Contains: `i18n_manager.py` (runtime locale switching), `clipboard_manager.py`

## Data Flow

**Recording and Transcription:**

1. User clicks Record in `FletApp` (`app/ui_flet/main_app.py`).
2. `FletApp._start_recording()` calls `AudioRecorder.start_recording(mode)`.
3. `sounddevice.InputStream` fires `_audio_callback` per block; RMS is computed and sent via `on_rms_update` callback to the VU meter widget (`app/ui_flet/vu_meter.py`).
4. User clicks Stop; `FletApp._stop_recording()` calls `AudioRecorder.stop_recording()`, which flushes frames to a temp `.wav` file.
5. A `threading.Thread` runs `_transcribe_worker(wav_path)`.
6. `_transcribe_worker` reads the active prompt and keywords from `Sidebar`, then calls `Transcriber.transcribe(wav_path, prompt_text, keywords, mode, on_chunk)`.
7. `Transcriber` checks `NetworkMonitor.is_online` and routes to Gemini or Whisper.
8. Gemini: audio uploaded via Files API, `generate_content_stream` yields chunks → `on_chunk` callback writes each chunk to the active tab's editor (`TabManager.insert_text_active`).
9. Whisper: `WhisperModel.transcribe` returns segments; full text inserted at once after stream completes.
10. `FletApp._reset_recording_ui()` restores button states on the main thread via `page.update()`.

**File Upload (non-recording):**

1. User clicks the upload button → `open_audio_file()` opens a native file dialog.
2. Selected path is stored in `FletApp._current_audio_path`.
3. When Stop/Transcribe is clicked, `_stop_recording` uses the stored path instead of calling `AudioRecorder.stop_recording()`.
4. Transcription proceeds identically from step 5 above.

**State Management:**
- No global state store. Each `FletApp` instance owns references to its service objects.
- UI state (recording flag, timer, current audio path) is held as instance attributes on `FletApp`.
- Persistent state (prompts, sessions) lives in SQLite via `app/database.py`.

## Key Abstractions

**Transcriber:**
- Purpose: Routes audio to the appropriate transcription backend, hiding backend selection from callers.
- File: `app/transcriber.py`
- Pattern: Strategy pattern — `mode` arg selects "auto" | "gemini" | "whisper"; auto mode falls back from Gemini to Whisper on network failure. Whisper model is lazy-loaded on first use.

**AudioRecorder:**
- Purpose: Abstracts microphone vs. system-audio capture into a uniform `start_recording(mode)` / `stop_recording() -> Path` API.
- File: `app/audio_recorder.py`
- Pattern: Two capture backends (sounddevice InputStream for mic; `parec` subprocess for Linux system audio). Both feed the same `_audio_callback` for RMS computation.

**NetworkMonitor:**
- Purpose: Provides a stable `is_online: bool` property updated by a background daemon thread.
- File: `app/network_monitor.py`
- Pattern: Observer — calls `on_status_change(bool)` callback only when status transitions.

**TabManager:**
- Purpose: Manages multiple transcription tabs, exposing `insert_text_active(text)` for thread-safe text insertion into the currently active tab.
- File: `app/ui_flet/tab_manager.py`

**Sidebar:**
- Purpose: Displays and manages user-defined prompts (with glossary keywords); exposes `get_active_prompt() -> dict` to callers.
- File: `app/ui_flet/sidebar.py`

## Entry Points

**Flet UI (primary):**
- Location: `main_flet.py`
- Triggers: `uv run python main_flet.py`
- Responsibilities: Validate config, initialize DB, call `ft.run(main, assets_dir="assets")` which hands a `ft.Page` to `init_app`.

**CustomTkinter UI (legacy):**
- Location: `main.py`
- Triggers: `uv run main.py`
- Responsibilities: Validate config, initialize DB, construct `MainWindow` and start the Tk mainloop.

## Error Handling

**Strategy:** Fail-fast at startup (config validation), graceful degradation at runtime (Gemini → Whisper fallback).

**Patterns:**
- `app/config.py` raises `RuntimeError` for missing required vars; both entry points catch it, print to stderr, and call `sys.exit(1)`.
- `Transcriber` wraps backend calls in `TranscriptionError`; auto mode silently falls back to Whisper; forced-mode raises to the caller.
- `AudioRecorder` CUDA load failures trigger an automatic CPU retry with `int8` compute type.
- UI workers catch `Exception` broadly and log to stdout (several `[DEBUG]` prints marked for removal).

## Cross-Cutting Concerns

**Logging:** `print()` statements with `[DEBUG]` prefix throughout core services; no structured logging library.
**Validation:** `app/audio_validator.py` gates file-upload paths; `app/config.py` gates startup.
**Authentication:** API key injected via `GOOGLE_API_KEY` env var; read once at import time from `app/config.py`.
**Internationalization:** `python-i18n` library with JSON locale files in `locales/`; locale set at startup, switchable at runtime via `i18n_manager.py`.
**Threading:** All long-running work (recording, transcription) runs in `daemon=True` threads; Flet UI updated via `page.update()` from worker threads.

---

*Architecture analysis: 2026-04-13*
