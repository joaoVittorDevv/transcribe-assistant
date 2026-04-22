# Architecture

**Pattern:** Single-window modular monolith with threading for I/O

## High-Level Structure

```
main.py
└── app.config (validates env, inits i18n)
    └── database.initialize_db()
    └── MainWindow (app.ui.main_window)
        ├── AudioRecorder (app.audio_recorder)
        ├── NetworkMonitor (app.network_monitor) — daemon Thread
        ├── Transcriber (app.transcriber)
        │   ├── Gemini backend (google-genai)
        │   └── Groq backend (groq + TextReviewerAgent)
        ├── AudioValidator (app.audio_validator) — Silero VAD
        └── VUMeter (app.ui.vu_meter)

Sub-windows (CTkToplevel):
├── PromptModal (app.ui.prompt_modal) — settings modal
└── HistoryWindow (app.ui.history_window) — session browser
```

## Threading Strategy

The app uses 3 background threads:

| Thread | Purpose | Communication |
|--------|---------|---------------|
| `AudioRecorder` callback | Sounddevice audio block callback | `_rms_queue` → `root.after()` polling |
| `TranscribeWorker` | Transcription API calls | `_ui_queue` → `root.after()` polling |
| `NetworkMonitor` | TCP connectivity check (daemon) | `on_status_change` callback → `_ui_queue` |

UI updates are always dispatched via `root.after()` / `self.after()` to ensure thread safety.

## Identified Patterns

### Queue-Based Thread→UI Communication

**Location:** `app/ui/main_window.py`
**Purpose:** Safe thread-to-UI communication without locks
**Implementation:**
```python
_ui_queue: queue.Queue = queue.Queue()

def _poll_ui_queue(self) -> None:
    try:
        while True:
            event, payload = _ui_queue.get_nowait()
            if event == "transcription_done":
                self._finish_transcription_ok(payload)
            # ...
    except queue.Empty:
        pass
    self.after(_POLL_MS, self._poll_ui_queue)
```

### Context Manager for DB Connections

**Location:** `app/database.py`
**Purpose:** Ensure connections close and rollback on error
**Implementation:**
```python
@contextmanager
def _connect() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

### Hybrid Routing with Fallback

**Location:** `app/transcriber.py`
**Purpose:** Reliable transcription with automatic failover
**Implementation:**
```python
def transcribe(...):
    if mode == "auto":
        try:
            return self._transcribe_groq(...)
        except TranscriptionError:
            return self._transcribe_gemini(...)
```

### Audio Validation with Dual Layer

**Location:** `app/audio_validator.py`
**Purpose:** Ensure audio files contain speech before spending API quota
**Implementation:**
- Layer 1: Silero VAD computes speech ratio via `faster_whisper.vad.get_speech_timestamps`
- Layer 2 (ambiguous 15-40%): Gemini classifies as fallback
- Thresholds: >40% accept, <15% reject, 15-40% ambiguous

### Delayed UI Init (Linux Fix)

**Location:** `app/ui/prompt_modal.py`, `app/ui/history_window.py`
**Purpose:** Fix CTkToplevel race condition on Linux/X11
**Implementation:**
```python
self.after(10, self._delayed_init)  # defer UI build
```

### Custom Tooltip (No Dependencies)

**Location:** `app/ui/main_window.py` → `_Tooltip` class
**Purpose:** Hover tooltip for icon buttons without external deps

## Data Flow

### Recording → Transcription → Persistence

1. User clicks record → `AudioRecorder.start_recording()` (background thread)
2. RMS callback → `_rms_queue` → `_poll_rms_queue()` → `VUMeter.set_level()`
3. User clicks stop → `AudioRecorder.stop_recording()` → temp WAV path
4. `TranscribeWorker` thread calls `Transcriber.transcribe()` → API returns text
5. Result posted to `_ui_queue` → `_finish_transcription_ok()` → text inserted in textbox
6. Debounced auto-save (1s delay) via `after()` → `database.overwrite_session_content()`

### Audio Import Flow

1. User clicks import → `open_audio_file()` (Zenity on Linux)
2. Format check → `AudioValidator.validate()`
3. Silero VAD computes speech ratio → if ambiguous (15-40%), Gemini classifies
4. Accepted → `TranscribeWorker` transcribes the file (not deleted after)
5. Rejected → status error shown, no transcription attempted

## Code Organization

**Approach:** Feature-based layered organization

| Directory | Purpose |
|-----------|---------|
| `app/` | Root package |
| `app/ui/` | CustomTkinter UI components |
| `app/agents/` | AI agents (TextReviewerAgent) |
| `app/utils/` | Utilities (clipboard, audio validation) |
| `app/database.py` | SQLite CRUD layer |
| `app/config.py` | Environment variables + i18n |
| `app/audio_recorder.py` | Audio capture |
| `app/audio_validator.py` | Audio validation (Silero VAD) |
| `app/transcriber.py` | Transcription routing |
| `app/network_monitor.py` | Connectivity monitoring |

## Module Boundaries

| Module | Responsibility | Public API |
|--------|---------------|------------|
| `audio_recorder` | Audio capture + RMS | `start_recording()`, `stop_recording()`, `current_rms`, `set_source()` |
| `transcriber` | Routing + API calls | `transcribe(audio_path, prompt_text, keywords, mode)`, `generate_title()` |
| `audio_validator` | Speech validation | `validate(audio_path) → ValidationResult` |
| `database` | SQLite CRUD | `create_session()`, `update_session()`, `get_all_sessions()`, prompts CRUD, keywords CRUD |
| `config` | Env vars + i18n | All `_*` vars (`GOOGLE_API_KEY`, etc.) |
| `agents` | AI review | `TextReviewerAgent.review()` |
| `network_monitor` | Connectivity | `is_online` property, `start()`, `stop()` |
| `ui/main_window` | UI orchestration | `MainWindow` class with all recording/transcription logic |
| `ui/vu_meter` | Audio level display | `VUMeter.set_level()` |
| `ui/prompt_modal` | Settings modal | `PromptModal` class |
| `ui/history_window` | Session browser | `HistoryWindow` class |
| `ui/native_dialog` | File picker | `open_audio_file()` |
