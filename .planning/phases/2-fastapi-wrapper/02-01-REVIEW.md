# Phase 2 Code Review

## Thread Safety: PASS
- `call_soon_threadsafe` correctly used for cross-thread queue push from background `threading.Thread` to async generator
- `_session_lock` used around every `_active_sessions` access
- `session_id` UUID generation outside lock is safe (not yet published)

**Concern:** `_whisper_model` instance variable is accessed from both the main thread (via `_get_whisper_model`) and background threads running `run_transcribe` - but since model loading completes before transcription starts, and faster-whisper's `transcribe()` is thread-safe, this is acceptable.

## Security: FAIL

**HIGH — Temp file leak on early disconnect:**
`transcription_events()` writes to a tempfile with `delete=False` but never deletes it in any cleanup path. If the client disconnects mid-stream, the generator is cancelled but the tempfile persists on disk.

```python
# Missing: finally block to clean up temp_path
# Current code has no guarantee of cleanup
```

**HIGH — Full file read into memory before size check:**
```python
audio_bytes = await audio.read()
if len(audio_bytes) > 100 * 1024 * 1024:  # 100MB loaded into RAM first
```

For a 500MB upload this loads the entire file before rejecting it. Use `fastapi.UploadFile` stream reading with a max_bytes check instead.

**MEDIUM — `TranscriptionStatusResponse.session_id: int | None` inconsistency:**
GET returns `session_id: None` always (hardcoded), despite receiving `session_id` as path parameter. Cosmetic but confusing.

## SSE Correctness: PASS

SSE format is correct:
```python
yield {"event": "chunk", "data": item}  # maps to event: chunk\ndata: <text>\n\n
yield {"event": "chunk", "data": "[DONE]"}
```

Generator cancellation is handled via FastAPI's StreamingResponse task cancellation when client disconnects — `queue.get()` will raise `asyncio.CancelledError`.

## Error Handling: PASS

Transcription errors are caught in `run_transcribe()` and sent as `[ERROR]` chunks:
```python
error_text = f"[ERROR] {exc}"
loop.call_soon_threadsafe(queue.put_nowait, error_text)
```

Missing sessions return 404 as expected.

## Resource Management: FAIL

**HIGH — Temp file never deleted:**
```python
with tempfile.NamedTemporaryFile(delete=False, suffix=...) as f:
    f.write(audio_bytes)
    temp_path = Path(f.name)
# temp_path has no cleanup in any code path
```

**MEDIUM — No `delete=True` alternative (would break open file handle):**
The `NamedTemporaryFile` approach is correct for sharing with subprocess, but cleanup must be added explicitly.

**LOW — Background thread properly daemonized:**
`thread = threading.Thread(target=run_transcribe, daemon=True)` — OK.

## Tests: FAIL

`tests/test_server_sse.py` does not exist. The plan specified 3 smoke tests but they were never created.

---

## Issues (with severity)

| Severity | Issue | Location |
|----------|-------|----------|
| HIGH | Temp file never deleted — file descriptor leak on disk | `app/server.py` ll.142-146 |
| HIGH | Full file read into memory before 100MB check (DoS vector) | `app/server.py` l.135 |
| MEDIUM | No cleanup path for temp file when client disconnects | `app/server.py` |
| MEDIUM | `session_id` always `None` in status response despite being in path | `app/server.py` l.181 |
| LOW | No test file exists for SSE endpoint | `tests/test_server_sse.py` |

---

## Recommendations

1. **Add tempfile cleanup** — Use a `try/finally` in `transcription_events` or an explicit cleanup after transcription completes:
   ```python
   finally:
       try:
           temp_path.unlink(missing_ok=True)
       except Exception:
           pass
   ```

2. **Stream file instead of reading fully** — Use chunked read with max_bytes enforcement:
   ```python
   audio_bytes = await audio.read(100 * 1024 * 1024 + 1)  # read up to 100MB+1
   if len(audio_bytes) > 100 * 1024 * 1024:
       raise HTTPException(status_code=413, detail="File too large")
   ```

3. **Fix session_id response** — Return the actual `session_id` string instead of `None`.

4. **Create `tests/test_server_sse.py`** — Add the 3 smoke tests from the plan to verify SSE content-type, 404 on missing session, and idempotent DELETE.

5. **Consider adding** `on_chunk` for Whisper segments (already partially implemented in `_transcribe_whisper` with `on_chunk(text + " ")` inside the segment loop).

---

## Summary

The core SSE streaming logic and thread-safe queue pattern are well-implemented. The main gaps are **resource cleanup** (tempfile leak) and **security** (full file read before size check). These should be fixed before merging.