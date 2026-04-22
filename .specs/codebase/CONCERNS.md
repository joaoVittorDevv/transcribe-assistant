# Concerns

**Last updated:** 2026-04-21

## High Priority

### C001: No Test Coverage

**Evidence:** `tests/` directory is empty; no pytest configuration
**Impact:** Regression risk; difficult to validate changes
**Fix approach:** Add unit tests for core modules (audio_recorder RMS, transcriber routing, database CRUD, audio_validator thresholds); integration tests with temp SQLite

---

### C002: No Type Checking Enforcement

**Evidence:** Type annotations present throughout but no `mypy` or `pyright` in CI
**Impact:** Type-related bugs may go undetected
**Fix approach:** Add `mypy` to dev dependencies; add type checking to CI pipeline

---

### C003: Groq 25MB File Size Limit Unhandled in UI

**Evidence:** `app/transcriber.py` checks file size but only raises `TranscriptionError` after recording completes
**Impact:** User records long audio, stops, then gets error — wasting time
**Fix approach:** Add file size estimation during recording or warn when approaching limit

## Medium Priority

### C004: Debug Print Statements in Production Code

**Evidence:** Multiple `print(f"[DEBUG] ...")` in `audio_recorder.py`, `transcriber.py`, `network_monitor.py`, `audio_validator.py`, `main_window.py`, `history_window.py`
**Impact:** Clutters output; minor performance overhead; potential info leak if sensitive data logged
**Fix approach:** Replace with `logging.debug()` or remove before production

---

### C005: No API Key Validation at Startup

**Evidence:** `app/config.py` validates keys via `_require()` but only raises `RuntimeError` if missing; app starts and may fail later on first transcription
**Impact:** Poor UX — user only discovers missing key when attempting transcription
**Fix approach:** Add startup health check that tests each API key

---

### C006: Thread Safety in NetworkMonitor

**Evidence:** `_is_online` accessed from both monitor thread and main thread without locks; `on_status_change` callback invoked from monitor thread
**Impact:** Potential race condition on status read/write; callback invoked from wrong thread
**Fix approach:** Add `threading.Lock()` around `_is_online` access; always post to `_ui_queue` from callback

---

### C007: Database Migrations Manual

**Evidence:** `app/database.py` uses `ALTER TABLE` try/except for migrations; no migration framework
**Impact:** Schema changes require code updates; old databases may be in inconsistent state
**Fix approach:** Use `alembic` or similar migration tool

---

### C008: sidebar.py Not Integrated

**Evidence:** `app/ui/sidebar.py` exists with prompt selection UI but is NOT loaded in `main_window.py`
**Impact:** Dead code; prompt selection via sidebar is unavailable to users
**Fix approach:** Either integrate sidebar into main_window layout or remove dead code

## Low Priority

### C009: faster-whisper Included But Not Used for Transcription

**Evidence:** `faster-whisper` in `pyproject.toml`; only `faster_whisper.audio` and `faster_whisper.vad` used (not transcription model); README mentions local transcription but code uses cloud only
**Impact:** Confusion about intended architecture; unused dependency adds install weight
**Fix approach:** Document that faster-whisper is VAD-only; or remove if Silero VAD from another source is preferred

---

### C010: Experimental Flet UI (`app/ui_flet/`) and Electron Scaffold (`electron/`)

**Evidence:** `app/ui_flet/` and `electron/` directories exist but are not loaded by `main.py`
**Impact:** Confusion about active UI stack; parallel maintenance burden if both are kept
**Fix approach:** Decide which UI path is primary; archive or remove the other

---

### C011: `_Tooltip` Helper Duplicated Pattern

**Evidence:** Tooltip implementation exists inline in `main_window.py`; but similar patterns may exist elsewhere
**Impact:** Code duplication if other widgets need tooltips
**Fix approach:** Extract to `app/ui/tooltip.py` or use a library

---

### C012: VUMeter Thread Safety Not Documented

**Evidence:** `VUMeter.set_level()` docstring says "NOT thread-safe — call from UI thread only"; RMS callback could theoretically call from wrong thread
**Impact:** In practice, RMS is queued via `_rms_queue` → `_poll_rms_queue()` which runs on UI thread — but the contract is fragile
**Fix approach:** Add explicit queue-based thread-safe interface to `VUMeter`
