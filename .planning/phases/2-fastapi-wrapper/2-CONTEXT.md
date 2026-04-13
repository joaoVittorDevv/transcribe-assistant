# Phase 2: FastAPI Backend Wrapper

**Gathered:** 2026-04-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Create a FastAPI HTTP server that wraps the existing `Transcriber` class and streams transcription text to the Electron frontend via Server-Sent Events (SSE), replicating the real-time streaming behavior already implemented in `app/ui/main_window.py`.

</domain>

<decisions>
## Implementation Decisions

### Streaming Strategy
- **D-01:** Server-Sent Events (SSE) — unidirectional, server → client only
- **D-02:** Plain text format — each SSE event carries a plain string chunk, no JSON wrapper

### Backend Integration
- **D-03:** FastAPI wraps the existing `Transcriber` class directly (from `app/transcriber.py`)
- **D-04:** Wrapped into the existing Python application process (not a separate service)
- **D-05:** SSE stream via `on_chunk` callback — the `Transcriber.transcribe()` already supports this callback internally when using Gemini streaming. Whisper returns all at once, so chunks are sent as they arrive from the model.

### Connection Resilience
- **D-06:** Frontend auto-reconnects on connection loss
- **D-07:** Exponential backoff for reconnection delay
- **D-08:** Server persists transcription state (session_id, tab content) so reconnects can resume

### Text Protocol
- **D-09:** Each SSE `data:` line is a plain UTF-8 text chunk
- **D-10:** Final chunk signaled by SSE `data: [DONE]` or connection close
- **D-11:** Error chunk format: `data: [ERROR] <message>`

### API Shape (TBD during planning)
- `POST /transcribe` — starts a transcription session, returns SSE stream
- `GET /transcribe/status` — returns current session status (TBD)
- `DELETE /transcribe/<session_id>` — cancels active session (TBD)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `app/transcriber.py` — Transcriber class with `on_chunk` callback support for Gemini streaming
- `app/ui/main_window.py` §handle_chunk + transcription_chunk event — current SSE-equivalent pattern already in use
- `app/config.py` — Configuration (API keys, model names, device settings)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Transcriber.transcribe(on_chunk=fn)` — already supports streaming via Gemini `generate_content_stream`, chunks passed to callback as they arrive
- `transcription_chunk` queue event in `main_window.py` — pattern for how the UI receives and inserts streaming text
- `_ui_queue.put(("transcription_chunk", (chunk_text, target_tab_name, request_id)))` — the queue-based approach for cross-thread text insertion

### Established Patterns
- Thread-based queue for cross-thread communication (used in main_window.py)
- `request_id` pattern to track which request a chunk belongs to (enables cancellation)

### Integration Points
- `Transcriber.transcribe()` is the main entry point — FastAPI would call this
- Audio files arrive from the Electron frontend via file upload
- SSE endpoint needs to run on a separate thread to not block Starlette/Uvicorn

### Creative Options
- Keep it minimal: one POST endpoint, SSE response, minimal state
- Or richer: session management, cancel endpoint, status endpoint

</code_context>

<specifics>
## Specific Ideas

- The existing CustomTkinter UI already streams text in real-time via `handle_chunk()` → `_ui_queue.put("transcription_chunk", ...)` → `_insert_transcription(chunk_text, ..., stream_chunk=True)`. The FastAPI wrapper should replicate this same flow for Electron.
- Gemini streaming already works — chunks come from `generate_content_stream` and go to `on_chunk`. Whisper chunks are not yet implemented (returns all at once) — decision needed on whether to add Whisper chunking or only stream Gemini.

</specifics>

<deferred>
## Deferred Ideas

- Whether Whisper should also support chunked streaming (currently returns all text at once) — can be a future enhancement after basic SSE works

</deferred>
