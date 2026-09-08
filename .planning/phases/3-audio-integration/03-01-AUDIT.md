# Phase 3 Audio Integration — Audit Report 01

**Date:** 2026-04-13
**Plan:** `.planning/phases/3-audio-integration/03-01-PLAN.md`
**Status:** NOT IMPLEMENTED — 0 / 7 files meet must-have criteria

---

## Summary

Phase 3 audio integration has **not been implemented**. Every file listed in the plan either does not exist, is unchanged from the previous phase, or contains only mock/hardcoded data. The entire audio IPC chain (audio_engine subprocess → Electron main → preload → renderer composable → Vue components) is absent.

---

## Must-Have Verification

### 1. audio_engine.py — JSON stdin/stdout, RMS events, graceful shutdown

**Status: MISSING**

`app/audio_engine.py` does not exist. The file is not present in the `app/` directory.

- No JSON stdin command loop
- No RMS event emission to stdout
- No SIGTERM graceful shutdown handler

**Verification:** `echo '{"action":"stop"}' | timeout 2 python app/audio_engine.py` returned exit code 1 (file not found).

---

### 2. Electron main spawns audio_engine at startup, restarts on death

**Status: NOT IMPLEMENTED**

`electron/src/main/index.ts` is unchanged from the previous phase. It only:
- Spawns the FastAPI SSE server (`uv run python -m app.server`)
- Has no `audioEngine` variable
- Has no `startAudioEngine()` / `stopAudioEngine()` functions
- No RMS JSON parsing from stdout
- No `webContents.send('rms-update', value)` IPC forwarding
- No restart-on-death logic
- No `mainWindow` module-level reference needed for IPC

---

### 3. Preload exposes audioCommand and onRmsUpdate

**Status: NOT IMPLEMENTED**

`electron/src/preload/index.ts` only exposes:
- `platform`
- `writeClipboard`

Missing entirely:
- `audioCommand(cmd)` — no `ipcRenderer.invoke('audio-command', ...)` bridge
- `onRmsUpdate(callback)` — no `ipcRenderer.on('rms-update', ...)` listener
- `openFilePicker(accept)` — no file dialog IPC

---

### 4. useTranscriptionState drives IDLE→RECORDING→TRANSCRIBING with real audio+SSE

**Status: NOT IMPLEMENTED — fully mocked**

`electron/src/renderer/composables/useTranscriptionState.ts` uses hardcoded mock data:
- No `electronAPI` import
- No `currentMode` ref
- No `rmsValue` ref
- `handleRecordClick()` transitions through states with `setTimeout`, inserting `MOCK_TEXT`
- No `electronAPI.audioCommand()` calls
- No `fetch()` to `http://localhost:18763/transcribe`
- No SSE parsing

---

### 5. AudioVisualizer receives real RMS values

**Status: NOT VERIFIABLE**

`AudioVisualizer.vue` is referenced in `BottomActionBar.vue` but was not in the audit scope. However, since `useTranscriptionState` has no `rmsValue` ref, there is no RMS source to bind to.

---

### 6. RecordButton has mic/system toggle with icons

**Status: NOT IMPLEMENTED**

`electron/src/renderer/components/bottom/RecordButton.vue` only renders:
- Microphone SVG (IDLE state)
- Stop square SVG (RECORDING state)
- Spinner SVG (TRANSCRIBING state)

No toggle button exists. No `mode` prop, no `mode-change` emit, no icon cycling between mic and speaker.

---

### 7. ImportAudio in TopBar between LanguageToggle and History

**Status: NOT IMPLEMENTED — button still in BottomActionBar**

`electron/src/renderer/components/topbar/TopActionButtons.vue` only has Copy and History buttons. ImportAudio is not present.

`electron/src/renderer/components/bottom/BottomActionBar.vue` still contains the mock ImportAudio button at lines 18-23 (the `glass-btn` with upload icon and `t('buttons.import_audio')` label).

---

## Additional Verification

### TypeScript Compilation

```
src/renderer/main.ts(2,17): error TS2307: Cannot find module './App.vue'
```

Only one error, unrelated to the Phase 3 files. All other Phase 3 files compile cleanly (they are incomplete/missing, not type-errored).

### audio_engine.py Execution

`echo '{"action":"stop"}' | timeout 2 python app/audio_engine.py` → exit code 1.

File does not exist.

---

## Files Status Table

| File | Status | Notes |
|------|--------|-------|
| `app/audio_engine.py` | **MISSING** | Does not exist |
| `electron/src/main/index.ts` | Not implemented | No audio_engine subprocess management |
| `electron/src/preload/index.ts` | Not implemented | No audioCommand, onRmsUpdate, openFilePicker |
| `electron/src/renderer/composables/useTranscriptionState.ts` | Not implemented | Fully mocked, no real IPC/audio/SSE |
| `electron/src/renderer/components/bottom/RecordButton.vue` | Not implemented | No mic/system toggle |
| `electron/src/renderer/components/bottom/BottomActionBar.vue` | Not implemented | ImportAudio not removed |
| `electron/src/renderer/components/topbar/TopActionButtons.vue` | Not implemented | ImportAudio not added |

---

## Conclusion

**Phase 3 audio integration requires full implementation from scratch.** None of the 7 must-have files meet the plan requirements. All 7 tasks (Tasks 1-7 in the plan) remain to be executed.
