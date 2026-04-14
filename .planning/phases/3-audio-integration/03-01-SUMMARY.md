# Phase 3: Audio Integration - Summary

## Files Created

- `app/audio_engine.py` - Python subprocess entry point for AudioRecorder. Controlled via stdin JSON commands (`{"action":"start","mode":"mic|system"}`, `{"action":"stop"}`). Emits `{"type":"rms","value":0.75}` and `{"type":"status","recording":bool,"wav_path":str}` JSON lines to stdout.

- `electron/src/renderer/types/global.d.ts` - Global TypeScript declarations for `window.electronAPI`, `AudioStatus`, and `ElectronAPI` interfaces used across the renderer.

## Files Modified

- `electron/src/main/index.ts` - Added `startAudioEngine()` / `stopAudioEngine()` management for the audio_engine subprocess. Forwards RMS updates to renderer via `webContents.send('rms-update')` and status events via `webContents.send('audio-status')`. Added IPC handlers for `audio-command`, `open-file-dialog`, and `read-file`. Audio engine auto-restarts on crash after 500ms.

- `electron/src/preload/index.ts` - Added `audioCommand()`, `onRmsUpdate()`, `onAudioStatus()`, `openFilePicker()`, and `readFile()` to the contextBridge electronAPI.

- `electron/src/renderer/composables/useTranscriptionState.ts` - Full state machine: IDLE→RECORDING (sends start command), RECORDING→TRANSCRIBING (sends stop, waits for wav_path via onAudioStatus, then POSTs to /transcribe and parses SSE chunks). Exports `rmsValue` ref for AudioVisualizer binding. Added `setMode()` for mic/system toggle.

- `electron/src/renderer/components/bottom/RecordButton.vue` - Already had mic/system toggle button added by linter. Exposes `mode` via `defineExpose({ mode })`. Cycles mic↔system on click, emits `mode-change`.

- `electron/src/renderer/components/topbar/TopActionButtons.vue` - Already had ImportAudio button added by linter. Fixed `importAudio()` to use `electronAPI.readFile()` for proper file reading via IPC, then POST to SSE endpoint with FormData.

- `electron/src/renderer/components/bottom/BottomActionBar.vue` - ImportAudio button already removed (only Reset remains in right section).

## Key Patterns

- audio_engine stdout → main process → renderer IPC (`rms-update`, `audio-status`)
- renderer → main → audio_engine stdin (`audio-command`)
- `wav_path` captured via `onAudioStatus` callback with polling interval
- SSE parsing in both `useTranscriptionState.stopAndTranscribe()` and `TopActionButtons.importAudio()`
- File reading via `electronAPI.readFile()` IPC (Node.js fs.readFileSync in main, ArrayBuffer returned to renderer)
