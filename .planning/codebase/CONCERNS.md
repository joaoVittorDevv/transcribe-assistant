# Codebase Concerns

**Analysis Date:** 2026-04-14

## Tech Debt

**Debug print statements throughout production code:**
- Files: `app/transcriber.py` (lines 82, 88, 98, 102, 104, 109, 113, 143, 169, 243, 256, 280, 299, 310, 314, 322, 360), `app/network_monitor.py` (lines 86-88, 92-94), `app/ui/main_window.py` (lines 509, 540, 546, 551, 619-621, 646-647, 651-652, 735, 1048-1050, 1068-1069), `app/audio_recorder.py` (line 108), `app/ui_flet/main_app.py` (lines 331, 333)
- Impact: Debug output pollutes stdout in production; no log levels configured
- Fix approach: Replace all `print("[DEBUG] ...")` with `logging.debug()` calls, or remove entirely

**Dead code after try/except/finally:**
- File: `app/transcriber.py` (line 186)
- Issue: `return final_text` executes after `finally` block cleans up; `final_text` may be undefined if exception occurs before assignment
- Impact: Potential `UnboundLocalError` on certain failure paths
- Fix approach: Remove the unreachable return statement

**Unused instance attribute `_last_was_stream`:**
- File: `app/transcriber.py` (lines 166, 224, 250)
- Issue: Set but never read within the class
- Impact: State tracking that provides no behavior
- Fix approach: Remove or actually use it for caller-side decisions

**Duplicate SSE parsing logic:**
- File: `electron/src/renderer/composables/useTranscriptionState.ts`, `electron/src/renderer/components/topbar/TopActionButtons.vue`
- Issue: SSE chunk parsing implemented separately in two files
- Impact: Code duplication, inconsistent error handling
- Fix approach: Extract to shared utility in `electron/src/renderer/utils/sseParser.ts`

**Dirty wav_path capture via polling:**
- File: `electron/src/renderer/composables/useTranscriptionState.ts`
- Issue: `setInterval` polling to wait for `wav_path` in audio-status events creates race condition window
- Fix approach: Use Promise/callback pattern that resolves when status event arrives

**Hardcoded Portuguese language:**
- File: `app/transcriber.py` (lines 220, 250)
- Issue: `language="pt"` hardcoded in `_transcribe_whisper`
- Impact: Non-Portuguese audio produces poor results
- Fix approach: Add `WHISPER_LANGUAGE` config; wire to UI language toggle

**Dual UI maintenance burden:**
- Files: `app/ui/` (CustomTkinter), `app/ui_flet/` (Flet)
- Impact: Changes to transcription flow must be applied twice
- Fix approach: Deprecate CustomTkinter; keep Flet as primary

---

## Security Considerations

**API key required at startup with no fallback:**
- File: `app/config.py` (line 49)
- Issue: `GOOGLE_API_KEY = _require("GOOGLE_API_KEY")` causes immediate `RuntimeError` if missing
- Impact: App fails to start even when using local Whisper only
- Recommendations: Make API key optional; gracefully disable Gemini when unavailable

**No audio file validation beyond extension check:**
- File: `app/ui/main_window.py` (line 1016)
- Issue: `is_supported_format()` only checks file extension; no magic bytes/header validation
- Impact: Malicious file renamed to `.wav` passes to transcription pipeline
- Recommendations: Validate WAV header before processing; enforce file size limits

**Temporary WAV files not securely cleaned on crash:**
- File: `app/audio_recorder.py` (lines 156-160)
- Issue: `tempfile.NamedTemporaryFile(delete=False)` leaves files on disk if process crashes
- Impact: Accumulated temp files fill disk over long sessions
- Recommendations: Use `tempfile.mkdtemp()` + explicit cleanup on shutdown

**IPC read-file allows arbitrary filesystem access:**
- File: `electron/src/main/index.ts` (lines 121-129)
- Issue: `ipcMain.handle('read-file')` reads any path provided by renderer
- Recommendations: Add path validation; restrict to project root or temp directory

**audio-engine stdin validation incomplete:**
- File: `app/audio_engine.py`
- Issue: `_handle_command()` only validates JSON parse — no schema validation on `action`/`mode` fields
- Recommendations: Add explicit allowlist validation before passing to `_start()`/`_stop()`

**No CORS protection on FastAPI SSE endpoint:**
- File: `app/server.py`
- Recommendations: Add explicit `CORSMiddleware` with configured allowed origins

---

## Performance Bottlenecks

**Whisper model loaded on first use (no warm-up):**
- File: `app/transcriber.py` (`_get_whisper_model()`)
- Problem: First transcription takes 5-30 seconds depending on model/hardware
- Impact: Poor UX on first recording
- Improvement path: Add `warm_up_whisper()` called at startup; show "loading model" state

**Gemini client instantiated per transcription:**
- File: `app/transcriber.py` (line 132)
- Problem: `genai.Client()` created on each call; no connection reuse
- Improvement path: Store client in `self._gemini_client`

**Monolithic main window class:**
- File: `app/ui/main_window.py` (1185 lines)
- Problem: Single class handles UI, recording, transcription, database, i18n
- Impact: Hard to test components independently
- Improvement path: Extract `TranscriptionController`, `TabStateManager`, `RecordingController`

**Busy-waiting UI polling loops:**
- File: `app/ui/main_window.py` (lines 669-700)
- Problem: `_poll_ui_queue` and `_poll_rms_queue` use `while True` with exception-based exit
- Impact: Constant CPU usage when idle
- Improvement path: Use `threading.Event` or `asyncio`

**Recursive threading.Timer for Flet timer:**
- File: `app/ui_flet/main_app.py` (lines 287-299)
- Problem: `_update_timer` schedules another timer each call
- Impact: Timer threads accumulate on exception
- Improvement path: Use single repeating timer with cancel on stop

---

## Fragile Areas

**Audio recorder system capture fallback silently fails:**
- File: `app/audio_recorder.py` (lines 107-109)
- Issue: If `parec` not found, falls through to microphone without user notification
- Why fragile: User selects system audio but gets microphone with no feedback
- Safe modification: Log warning when falling back; expose fallback status to UI

**Flet transcription worker ignores request invalidation:**
- File: `app/ui_flet/main_app.py` (lines 342-367)
- Issue: No `request_id` cancellation check (CustomTkinter has it)
- Why fragile: Cancel during transcription could overwrite with stale results
- Safe modification: Track and validate `request_id` like CustomTkinter does

**Transcriber title generation swallows all exceptions:**
- File: `app/transcriber.py` (lines 335-361)
- Issue: `generate_title` catches `Exception` and returns fallback silently
- Why fragile: Caller cannot distinguish failure modes
- Safe modification: Add specific exception handling; return `None` on failure

**Database migrations use bare `except` clauses:**
- File: `app/database.py` (lines 79-80, 84-85)
- Issue: `except sqlite3.OperationalError: pass` masks all errors
- Why fragile: Other `OperationalError` variants (e.g., locked database) silently ignored
- Safe modification: Check specific error message

**Sidebar prompt retrieval has no validation:**
- File: `app/ui_flet/main_app.py` (lines 343-345)
- Issue: `get_active_prompt()` result used without null check
- Why fragile: `None` result causes `TypeError` on `prompt_data["texto_prompt"]`
- Test coverage: No test for missing/invalid prompt selection

**FastAPI server has no auto-restart on crash:**
- File: `electron/src/main/index.ts`
- Issue: `startServer()` logs errors but does not restart
- Trigger: Unhandled exception kills subprocess
- Workaround: Electron app restart required

---

## Scaling Limits

**No session pruning or archival:**
- File: `app/database.py`
- Issue: All sessions stored indefinitely; no pagination or limits
- Current capacity: ~10,000 sessions before UI slowdown
- Scaling path: Add pagination to `get_all_sessions()`; implement soft-delete

**Audio temp files accumulate on long-running sessions:**
- File: `app/audio_recorder.py` (lines 156-160)
- Issue: `delete=False` on tempfile; only deleted on explicit `unlink`
- Current capacity: Unlimited until disk full (~1MB/minute)
- Scaling path: Use in-memory ring buffer; cleanup on shutdown

**Subprocess management assumes single window:**
- File: `electron/src/main/index.ts`
- Issue: One `audioEngine` subprocess per app; multi-window would spawn duplicates
- Scaling path: Use Electron's `utilityProcess` API or shared process

**No limit on concurrent transcription requests:**
- File: `app/server.py`
- Issue: `/transcribe` has no queue or concurrency limit
- Limit: Multiple rapid requests could overwhelm GPU memory
- Scaling path: Add semaphore-based concurrency limiting

---

## Dependencies at Risk

**faster-whisper GPU loading with partial CUDA:**
- File: `app/transcriber.py` (lines 226-256)
- Risk: `lib` in error message detection is too broad; unrelated errors caught
- Impact: CUDA error without "lib" in message bypasses fallback
- Migration plan: Use explicit `cuda.is_available()` check instead of exception parsing

**CustomTkinter threading model conflicts with audio callbacks:**
- File: `app/ui/main_window.py` (lines 169-198)
- Risk: RMS callback from sounddevice thread while UI updates on main thread
- Impact: Race conditions cause UI flickering under load
- Mitigation: Uses `queue.Queue` + `root.after()` marshaling

**Gemini API timeout hardcoded at 100 seconds:**
- File: `app/transcriber.py` (line 134), `app/config.py`
- Risk: Large audio files may exceed timeout
- Migration plan: Make `GEMINI_TIMEOUT` configurable

---

## Test Coverage Gaps

**No unit tests for audio_engine.py:**
- Untested: JSON command parsing, RMS event emission, SIGTERM graceful shutdown
- Files: `app/audio_engine.py`
- Risk: Changes to AudioRecorder API break audio engine silently
- Priority: High

**No integration tests for IPC chain:**
- Untested: Full audio_engine -> main -> preload -> renderer IPC path
- Files: `electron/src/main/index.ts`, `electron/src/preload/index.ts`
- Risk: RMS events drop silently in production
- Priority: High

**No unit tests for Transcriber routes:**
- Untested: `transcribe()` with modes (auto, gemini, whisper), fallback paths
- Untested: `generate_title()` error handling
- Files: `app/transcriber.py`
- Risk: Transcription routing bugs go undetected
- Priority: High

**No tests for database operations:**
- Untested: CRUD with foreign key constraints, session management
- Files: `app/database.py`
- Priority: Medium

**No tests for SSE streaming error states:**
- Untested: `[ERROR]` frame handling, malformed SSE, connection reset mid-stream
- Files: `electron/src/renderer/composables/useTranscriptionState.ts`
- Risk: UI hangs on transcription errors
- Priority: Medium

**No tests for cancellation flows:**
- Untested: Transcription cancellation in CustomTkinter, request_id invalidation
- Files: `app/ui/main_window.py`
- Priority: High

---

## Known Bugs

**Transcriber returns empty text in auto mode:**
- Symptom: Empty transcription appended when Gemini fails but fallback succeeds
- Files: `app/transcriber.py`, `app/ui/main_window.py`
- Trigger: Network timeout from Gemini API
- Workaround: Manual retry

**Flet VU meter does not reset after cancellation:**
- Symptom: VU meter stays lit at last level after cancel pressed
- File: `app/ui_flet/main_app.py` (line 381)
- Trigger: Click cancel during recording
- Workaround: Start new recording to refresh meter

**Language toggle state not persisted:**
- Symptom: Language reverts to PT on app restart
- File: `app/config.py`
- Workaround: None

**Transcription cancellation race in CustomTkinter:**
- File: `app/ui/main_window.py` (lines 710-711)
- Issue: Request ID check at queue drain time, not transcription time
- Impact: Completed transcription between worker finish and queue drain invalidates incorrectly

---

## Phase 3 Audio Integration Concerns

**Phase 3 audit shows zero implementation:**
- Source: `.planning/phases/3-audio-integration/03-01-AUDIT.md`
- Impact: All 7 tasks (audio_engine.py, IPC wiring, RecordButton toggle, ImportAudio move) are NOT IMPLEMENTED
- Current state: `audio_engine.py` now exists with proper stdin/stdout JSON; IPC wiring and Vue components are partially implemented per current git status
- Action required: Full implementation per `03-01-PLAN.md` with threat model (T-3-01 through T-3-04)

**Audio device not released on unexpected exit:**
- File: `app/audio_engine.py` (depends on `app/audio_recorder.py`)
- Issue: If audio_engine crashes or killed without SIGTERM, `AudioRecorder` may not close `pyaudio.Stream`
- Trigger: Kill -9 or crash during recording
- Workaround: Restart Electron app to reset audio device

**Whisper model never unloaded:**
- File: `app/transcriber.py` (`_whisper_model` attribute)
- Issue: Once loaded, model remains in memory for session lifetime
- Impact: Memory grows if switching between Gemini/Whisper repeatedly
- Fix approach: Add `_unload_whisper()` method; call when switching to Gemini if idle

---

## Missing Error Handling

**No validation of WAV file integrity before transcription:**
- Issue: Corrupted or empty WAV files passed to Whisper/Gemini
- Impact: API errors or unhelpful transcriptions
- Missing: File size > 0 check; WAV header validation; duration check

**No handling of database lock conflicts:**
- Issue: `OperationalError: database is locked` propagates unhandled
- File: `app/database.py`
- Impact: Session save fails silently on concurrent writes
- Missing: Retry logic or user-facing error message

---

*Concerns audit: 2026-04-14*