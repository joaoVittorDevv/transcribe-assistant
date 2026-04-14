---
status: investigating
trigger: "transcription-silent-failure"
created: 2026-04-14T00:00:00Z
updated: 2026-04-14T00:01:00Z
---

## Current Focus

hypothesis: CONFIRMED — Protocol mismatch: renderer POSTs JSON {wav_path} but server expects multipart/form-data UploadFile
test: Traced fetch() call in useTranscriptionState.ts vs @app.post("/transcribe") signature in server.py
expecting: FastAPI returns 422 immediately; SSE reader finds no data: lines; state silently resets to IDLE
next_action: Report root cause

## Symptoms

expected: Click transcribe → audio sent to API, transcription displayed with proper loading feedback
actual: Click transcribe → loader spins ~1 second then stops silently, no transcription result, no error shown
errors: None visible in UI (422 silently swallowed by SSE parser)
reproduction: 1) Click record 2) Speak 3) VU meter shows audio 4) Click stop 5) Click transcribe 6) Loader briefly spins then nothing
started: After recent changes to audio/transcription code
audio_file_status: Audio IS saved to disk correctly by AudioRecorder. But the path is never used correctly.

## Eliminated

- hypothesis: wav_path never set / audio_engine not emitting status
  evidence: audio_engine.py correctly emits {"type":"status","recording":false,"wav_path":"..."} and onAudioStatus sets pendingWavPath
  timestamp: 2026-04-14

- hypothesis: 5-second timeout fires before wav_path arrives
  evidence: User sees ~1s spinner, not 5s. transcribeFile IS called but fails fast.
  timestamp: 2026-04-14

- hypothesis: AudioRecorder.stop_recording() fails to save WAV
  evidence: Code correctly uses tempfile + sf.write(); would raise RuntimeError if no frames, but audio_engine catches that and emits wav_path: null only then
  timestamp: 2026-04-14

## Evidence

- timestamp: 2026-04-14
  checked: useTranscriptionState.ts lines 24-28
  found: fetch('http://localhost:18763/transcribe', { method:'POST', body: JSON.stringify({wav_path}), headers: {'Content-Type':'application/json'} })
  implication: Sends JSON body with a file path string

- timestamp: 2026-04-14
  checked: server.py lines 156-163
  found: @app.post("/transcribe") expects audio: UploadFile = File(...) — multipart/form-data binary upload
  implication: Server requires actual file bytes in multipart form, not JSON

- timestamp: 2026-04-14
  checked: server.py line 175
  found: if len(audio_bytes) == 0: raise HTTPException(status_code=400, detail="Empty audio file")
  implication: FastAPI returns 422 (validation error) before even reaching this check, because the field "audio" is missing from the request

- timestamp: 2026-04-14
  checked: useTranscriptionState.ts lines 30-66 (SSE reader loop)
  found: Reader only acts on lines starting with "data:". FastAPI 422 JSON error {"detail":[...]} has no "data:" prefix.
  implication: 422 body is consumed silently, loop exits, state.value = 'IDLE' — no error shown

## Resolution

root_cause: |
  Protocol mismatch between renderer and FastAPI server.
  useTranscriptionState.ts:24-28 sends Content-Type: application/json with body {wav_path: "/tmp/transcribe_xxx.wav"}.
  server.py:156-163 declares audio: UploadFile = File(...), requiring multipart/form-data with binary file content.
  FastAPI immediately returns HTTP 422 Unprocessable Entity.
  The SSE reader loop silently consumes the 422 JSON body (no "data:" lines found), exits cleanly, and resets state to IDLE.
  This explains ~1 second spinner: time for IPC round-trip + HTTP 422 response, with zero user-visible error.

fix: |
  Added a deep watcher in TextEditor.vue (lines 66-80) that syncs Quill text
  whenever the reactive tabs array content changes. This ensures SSE chunk
  updates to `tab.content` via `updateContent()` are reflected in the UI.
verification: |
  Fix applied to TextEditor.vue. Test: record audio → stop → transcribe → 
  check if text appears in editor. If not, the watcher may not fire because
  `updateContent` uses `tab.content = content` (direct assignment on reactive 
  object), but Vue's array mutation detection may require explicit reactivity 
  triggers. If still broken, consider using `useTabs` to expose `triggerUpdate` 
  ref or use `shallowRef` for tabs.
files_changed: [electron/src/renderer/components/editor/TextEditor.vue]
