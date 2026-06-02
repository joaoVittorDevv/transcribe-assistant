# Transcription Flow and Integrity Analysis

This document traces how audio transcription works across the Electron frontend and Python backend, highlighting data transit, technologies, and mechanisms that guarantee text integrity and order.

## 1. Overview of the Architecture
The system consists of a hybrid desktop application combining:
- **Frontend**: Electron application built with Vue, TypeScript, and Vite.
- **Backend (SSE Server)**: A FastAPI ASGI application running under Uvicorn (`app/server.py`).
- **Audio Engine**: A standalone Python process (`app/audio_engine.py`) managing recording.

Communication is decoupled:
- Electron launches both Python processes as subprocesses (`electron/src/main/index.ts:startServer()`, `electron/src/main/index.ts:startAudioEngine()`).
- Electron main and Audio Engine communicate via stdout/stdin JSON-lines IPC.
- Electron frontend (renderer) communicates with the SSE Server via standard HTTP REST and Server-Sent Events (SSE).

## 2. Step-by-Step Data Flow

### A. Audio Capture and File Generation
1. The user interacts with the UI in the frontend. It triggers `electron/src/renderer/composables/useTranscriptionState.ts:startRecording()`.
2. The frontend sends an IPC command `api.audioCommand({ action: 'start', mode: currentMode })` to the Electron main process, which forwards it to `app/audio_engine.py` over stdin.
3. `app/audio_recorder.py:start_recording()` uses `sounddevice` to capture audio from the selected source (microphone, system audio monitor, or both in dual mode).
4. When the user stops recording:
   - `audioCommand({ action: 'stop' })` is sent.
   - `app/audio_recorder.py:stop_recording()` concatenates recorded frames using `numpy.concatenate()` and writes them into mono WAV files (16kHz sample rate) via `soundfile` inside the configured `VAULT_PATH`.
   - The audio engine writes a JSON status payload containing the generated WAV file path(s) to stdout.
   - Electron main receives this path and forwards it to the renderer via IPC (`audio-status`).

### B. Transit from Frontend to Backend
1. The frontend (`useTranscriptionState.ts:transcribeFile()`) reads the WAV file from disk using `api.readFile(wavPath)` (which returns an `ArrayBuffer`).
2. It packs the audio data into `FormData` as a `Blob` and sends a `POST /transcribe` (or `/transcribe/dual`) HTTP request to the FastAPI server at `http://localhost:18763`.
3. In `app/server.py:transcribe()`, FastAPI reads the uploaded stream in chunks of 1MB up to 100MB to enforce memory safety.
4. The received bytes are saved into a temporary WAV file using `tempfile.NamedTemporaryFile`.

### C. Processing and Transcription Routing
1. The FastAPI endpoint invokes `app/transcriber.py:Transcriber:transcribe()` on a background thread (`threading.Thread`).
2. The `Transcriber` decides the backend routing:
   - **Google Gemini**: Standard route, forced for audios > 10 mins or dual mode. Audio is uploaded to Gemini Files API via `client.files.upload()`, then streamed using `client.models.generate_content_stream()`.
   - **Groq Whisper**: Fast route for short audio (<= 10 mins). Groq processes the audio as a single chunk using `whisper-large-v3-turbo` in a single blocking API call, and optionally passes the text to `TranscriptionReviewAgent` for punctuation and grammar correction.

### D. Return Flow (Backend to Frontend)
1. The backend streams transcription chunks and status updates back to the frontend using **Server-Sent Events (SSE)** via FastAPI's `StreamingResponse`.
2. The frontend receives the stream, decodes it using `TextDecoder`, parses the SSE lines, and immediately inserts the chunk text into the active editor at the cursor position via `api.insertTextAtCursor(data, targetTabId)`.
3. Once completed, a `[DONE]` event is sent, and the frontend cleans up the local files.

## 3. Technologies Used
- **Frontend UI**: Electron, Vue 3, Vite, TailwindCSS.
- **Audio Capture & Save**: `sounddevice`, `soundfile`, `numpy`, PulseAudio/PipeWire monitor (`parec` utility).
- **Backend Framework**: FastAPI (Uvicorn, Pydantic, CORS Middleware).
- **AI Transcription Providers**:
  - `google-genai` (Gemini API for long-audio, dual-audio diarization, and default transcription).
  - `groq` (Whisper API for fast, short transcription).
- **Database**: SQLite (managed by `app/database.py`).

## 4. Mechanisms for Text Integrity and Ordering
- **Single-chunk Audio Processing**: Unlike chunk-by-chunk local Whisper models that suffer from stitching artifacts, the entire audio file is sent to Gemini (via Files API) or Groq Whisper (via single API post). This ensures 100% context preservation and avoids out-of-order text compilation during recording.
- **FastAPI Thread-to-Async Queue Integration**: In `app/server.py`, the transcription is run in a background thread to prevent blocking the async event loop. To transit transcription chunks back to the async generator safely, the code uses `asyncio.Queue` and `running_loop.call_soon_threadsafe(queue.put_nowait, ("CHUNK", chunk_text))`. This ensures FIFO (First-In, First-Out) ordering of all tokens.
- **Sequenced SSE Stream Consuming**: SSE delivers events in a single HTTP connection. The browser/Node stream reader (`TextReader.read()`) reads the TCP stream sequentially, meaning the chunks cannot be out of order.
- **Cursor Tracking and Insertion Point Reset**: The frontend uses `api.resetInsertionPoint()` before starting and calls `api.insertTextAtCursor()` on every chunk, ensuring that chunks are appended exactly where the cursor is, maintaining typographic integrity.
- **Dual Mode Merged Diarization**: In dual mode, both mic and sys audio files are uploaded to Gemini. The system instructions (`GEMINI_DUAL_AUDIO_INSTRUCTION`) force Gemini to reconstruct the conversational turns in a single, ordered timeline using speaker markers (`@Usuario:` / `@Interlocutor N:`).

## 5. Known Gotchas (Updated 2026-06-01)

### 5.1 TipTap insertContentAt interprets text as Markdown
- `TextEditor.vue:223` — `ed.commands.insertContentAt(pos, text)` treats the string as rich content, not plain text.
- Chunks containing `---` (diarization markers), `@` prefixes, or mid-word splits may be parsed as Markdown/HTML by the TipTap Markdown extension.
- This causes text truncation and reordering, especially when chunks arrive mid-word (e.g., "otecas" instead of "bibliotecas").
- **Fix**: Insert as `[{ type: 'text', text: text }]` to force plain text treatment.

### 5.2 Multi-line SSE chunks inflate ProseMirror position tracking
- `_sse_frame()` splits `\n` into separate `data:` lines per SSE spec.
- The frontend re-joins them with `\n` (correct), but TipTap converts each `\n` into a `<p>` node.
- Each `<p>` adds +2 to ProseMirror doc size (open tag + close tag), so `sizeAfter - sizeBefore > text.length`.
- `transcriptionInsertIndex` advances too far, causing gaps between chunks.

### 5.3 Copy button uses Web Clipboard API which can fail silently in Electron
- `useClipboard.ts` uses `navigator.clipboard.writeText()` — requires focused document + clipboard-write permission.
- Fallback `document.execCommand('copy')` is deprecated.
- No visual feedback on success or failure.
- **Fix**: Use `electron.clipboard.writeText()` via IPC for reliability.

### 5.4 Clear button has race condition during active transcription
- `handleReset()` in `BottomActionBar.vue` does NOT reset `transcriptionInsertIndex` or abort active transcription.
- If user clicks Clear during transcription, chunks keep arriving and insert with a stale position index.
- `clearContent(true)` triggers `onUpdate` which can race with the watcher sync loop.

### 5.5 SSE parser is duplicated 3x across transcribeFile, transcribeDual, importAndTranscribe
- ~150 lines × 3 = ~450 duplicated lines in `useTranscriptionState.ts`.
- Fixes applied to one flow may not be applied to the others.

### 5.6 IPC insertTextAtCursor is fire-and-forget
- `preload/index.ts:69` — `ipcRenderer.send()` returns `Promise.resolve(true)` immediately.
- No backpressure mechanism if editor is slow to process chunks.
- If `mainWindow` is null/destroyed, messages are silently dropped.
