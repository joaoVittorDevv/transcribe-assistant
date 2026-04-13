# Codebase Concerns

**Analysis Date:** 2026-04-13

## Tech Debt

**Debug print statements left in production code:**
- Files: `app/transcriber.py` (lines 82, 88, 98, 102-105, 109-113, 143, 169, 236-238, 248, 266, 285-286, 296, 300-301, 308-309), `app/network_monitor.py` (lines 86-88, 92-94), `app/ui/main_window.py` (lines 509, 540, 546, 551, 619-621, 646-647, 651-652, 735, 1048-1050, 1068-1069), `app/audio_recorder.py` (line 108), `app/ui_flet/main_app.py` (lines 331, 333)
- Impact: Debug output pollutes logs in production; no log levels configured
- Fix approach: Replace all `print("[DEBUG] ...")` with proper `logging.debug()` calls, or remove entirely

**Hardcoded Portuguese language in Whisper:**
- Files: `app/transcriber.py` (lines 220, 244)
- Issue: `language="pt"` is hardcoded in two places inside `_transcribe_whisper`
- Impact: Whisper transcription will always use Portuguese regardless of actual audio language
- Fix approach: Accept language as a parameter or derive from prompt settings

**Dual UI maintenance burden:**
- Files: `app/ui/` (CustomTkinter), `app/ui_flet/` (Flet)
- Issue: Two parallel UI implementations with duplicated business logic
- Impact: Changes to transcription flow must be applied twice; bugfixes can diverge
- Fix approach: Deprecate one UI stack; keep only Flet as primary

**Dead code after try/except/finally:**
- File: `app/transcriber.py` (line 186)
- Issue: `return final_text` executes after `finally` block cleans up; `final_text` may be undefined
- Impact: Potential `UnboundLocalError` if exception occurs before `final_text` assignment
- Fix approach: Remove the unreachable return statement

**Unused instance attribute:**
- File: `app/transcriber.py` (line 166, 224, 250)
- Issue: `self._last_was_stream` is set but never read within the class
- Impact: State tracking that provides no behavior
- Fix approach: Remove if not needed, or use it for caller-side decisions

---

## Security Considerations

**API key required at startup with no fallback:**
- File: `app/config.py` (line 49)
- Issue: `GOOGLE_API_KEY = _require("GOOGLE_API_KEY")` causes immediate `RuntimeError` if missing
- Impact: App fails to start without valid key even when only using local Whisper mode
- Current mitigation: None
- Recommendations: Make API key optional; gracefully disable Gemini when unavailable

**No audio file validation beyond extension check:**
- File: `app/ui/main_window.py` (line 1016)
- Issue: `is_supported_format()` only checks file extension; no magic bytes/header validation
- Impact: Malicious file could be renamed to `.wav` and passed to transcription pipeline
- Recommendations: Validate WAV header before processing; enforce file size limits

**Temporary WAV files not securely cleaned on crash:**
- File: `app/audio_recorder.py` (lines 156-160)
- Issue: `tempfile.NamedTemporaryFile(delete=False)` leaves files on disk if process crashes
- Impact: Accumulated temporary audio files could fill disk over long sessions
- Recommendations: Use `tempfile.mkdtemp()` + explicit cleanup on shutdown, or `delete=True` with keepalive mechanism

---

## Performance Bottlenecks

**Monolithic main window class:**
- File: `app/ui/main_window.py` (1185 lines)
- Problem: Single `MainWindow` class handles UI layout, recording, transcription, database, i18n, and tooltips
- Cause: No separation between concerns (e.g., `_Tooltip` is a nested class, but most logic is in one class)
- Impact: Hard to test components independently; slow CI if testing requires full window
- Improvement path: Extract `TranscriptionController`, `TabStateManager`, `RecordingController` as separate classes

**Busy-waiting UI polling loops:**
- File: `app/ui/main_window.py` (lines 669-700)
- Issue: `_poll_ui_queue` and `_poll_rms_queue` use `while True` with `queue.Empty` exceptions
- Impact: Constant CPU usage even when idle; could cause battery drain on laptops
- Improvement path: Use `threading.Event` or `asyncio` with proper wait semantics

**Whisper model reloaded per-request under certain error conditions:**
- File: `app/transcriber.py` (lines 258-266)
- Issue: `_force_cpu_model()` replaces model without checking if already CPU
- Impact: Unnecessary reinitialization on repeated CUDA failures
- Improvement path: Add flag to prevent redundant reloads

**Recursive threading.Timer for Flet timer:**
- File: `app/ui_flet/main_app.py` (lines 287-299)
- Issue: `_update_timer` schedules another `threading.Timer(0.5, ...)` every call
- Impact: Timer threads accumulate if exception occurs; potential memory leak
- Improvement path: Use single repeating timer with cancel on stop

---

## Fragile Areas

**Audio recorder system capture fallback silently fails:**
- File: `app/audio_recorder.py` (lines 107-109)
- Issue: If `parec` is not found, falls through to microphone without user notification
- Why fragile: User selects system audio mode but gets microphone audio with no feedback
- Safe modification: Log warning when falling back; expose fallback status to UI
- Test coverage: No test for system audio mode on Linux without `parec`

**Flet transcription worker ignores request invalidation:**
- File: `app/ui_flet/main_app.py` (lines 342-367)
- Issue: Unlike CustomTkinter version, Flet has no `request_id` cancellation check
- Why fragile: If user cancels during transcription, stale results could overwrite current tab
- Safe modification: Track and validate `request_id` like CustomTkinter does

**Transcriber title generation swallows all exceptions:**
- File: `app/transcriber.py` (lines 321-347)
- Issue: `generate_title` catches `Exception` and returns hardcoded fallback with only `print` logging
- Why fragile: Network timeout or API error is silently ignored; caller cannot distinguish failure modes
- Safe modification: Add specific exception handling; consider returning `None` on failure instead of fallback string

**Database migrations use bare `except` clauses:**
- File: `app/database.py` (lines 79-80, 84-85)
- Issue: `except sqlite3.OperationalError: pass` masks all errors, not just "column exists"
- Why fragile: Other `OperationalError` variants (e.g., locked database) would be silently ignored
- Safe modification: Check specific error message or use `ALTER TABLE IF NOT EXISTS` syntax

**Sidebar prompt retrieval has no validation:**
- File: `app/ui_flet/main_app.py` (lines 343-345)
- Issue: `self.sidebar.get_active_prompt()` result directly used without null check
- Why fragile: If sidebar returns `None`, accessing `prompt_data["texto_prompt"]` raises `TypeError`
- Test coverage: No test for missing/invalid prompt selection

---

## Scaling Limits

**No session pruning or archival:**
- File: `app/database.py`
- Issue: All sessions stored indefinitely; no pagination, limits, or cleanup
- Current capacity: Practical limit ~10,000 sessions before UI slowdown
- Limit: Disk space and memory for loading session list
- Scaling path: Add pagination to `get_all_sessions()`; implement soft-delete or archival

**Audio temp files accumulate on long-running sessions:**
- File: `app/audio_recorder.py` (lines 156-160)
- Issue: `delete=False` on tempfile; only deleted on explicit `unlink` in worker
- Current capacity: Unlimited until disk full
- Limit: Disk space (~1MB per minute of audio)
- Scaling path: Use in-memory ring buffer for short recordings; cleanup on app shutdown

---

## Dependencies at Risk

**faster-whisper GPU loading with partial CUDA:**
- File: `app/transcriber.py` (lines 226-256)
- Risk: `lib` in error message detection is too broad; could catch unrelated errors
- Impact: If CUDA error message does not contain "lib", fallback to CPU never triggers
- Migration plan: Use explicit CUDA availability check instead of exception message parsing

**CustomTkinter threading model conflicts with audio callbacks:**
- File: `app/ui/main_window.py` (lines 169-198)
- Risk: RMS callback called from sounddevice thread while UI updates happen on main thread
- Impact: Under high load, race conditions could cause UI flickering or crashes
- Mitigation: Uses `queue.Queue` to safely marshal updates to main thread via `root.after()`

---

## Test Coverage Gaps

**No unit tests for critical paths:**
- Untested: `Transcriber.transcribe()` with all three modes (auto, gemini, whisper)
- Untested: `Transcriber.generate_title()` error handling
- Untested: `database.py` CRUD operations with foreign key constraints
- Untested: `AudioRecorder` system audio mode (`parec` fallback path)
- Untested: `main_window.py` transcription cancellation flow
- Risk: Bugs in transcription routing or database operations go undetected
- Priority: High for `Transcriber`; Medium for database; High for cancellation

**No integration tests:**
- Untested: Full recording -> transcription -> save session flow
- Untested: Offline mode auto-fallback from Gemini to Whisper
- Risk: User-facing workflows break without notice
- Priority: High

---

## Known Bugs

**Transcriber returns `None` text silently in auto mode:**
- Symptom: Empty transcription appended when Gemini fails in auto mode but fallback succeeds
- Files: `app/transcriber.py`, `app/ui/main_window.py` (line 713)
- Trigger: Network timeout from Gemini API
- Workaround: Manual retry; transcription stored correctly on retry

**Flet VU meter does not reset after cancellation:**
- Symptom: VU meter stays lit at last level after cancel button pressed
- File: `app/ui_flet/main_app.py` (line 381)
- Trigger: Click cancel during recording
- Workaround: Start new recording to refresh meter

**Language toggle state not persisted:**
- Symptom: Language reverts to PT on app restart
- File: `app/config.py` (line 56)
- Trigger: App restart
- Workaround: None

---

## Missing Error Handling

**No validation of WAV file integrity before transcription:**
- Issue: Corrupted or empty WAV files passed directly to Whisper/Gemini
- Files: `app/transcriber.py`, `app/ui/main_window.py`
- Impact: API errors or unhelpful transcriptions
- Missing: File size > 0 check; WAV header validation; duration check

**No handling of database lock conflicts:**
- Issue: SQLite `OperationalError: database is locked` propagates unhandled
- File: `app/database.py`
- Impact: Session save fails silently if concurrent writes occur
- Missing: Retry logic or user-facing error message

**Transcription cancellation race in CustomTkinter:**
- Issue: Request ID check happens at queue drain time, not at transcription time
- File: `app/ui/main_window.py` (lines 710-711)
- Impact: If transcription completes between worker finishing and queue drain, invalidation check passes incorrectly
- Missing: Atomic cancellation token passed to worker thread

---

*Concerns audit: 2026-04-13*
