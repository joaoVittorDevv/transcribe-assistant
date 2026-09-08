# Phase 3: Audio Integration - Context

**Gathered:** 2026-04-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Integrar a captura de áudio (microfone + sistema) com o backend FastAPI SSE já implementado na Phase 2, expondo tudo na interface Electron. O utilizador clica para gravar → Electron orchestrator comunica com Python subprocess → AudioRecorder captura áudio (mic ou system) → ficheiro WAV enviado para POST /transcribe → SSE streaming insere texto no editor. Também reordenar botões na interface.

</domain>

<decisions>
## Implementation Decisions

### Audio Source Selection
- **D-31:** Toggle junto ao botão de gravar — permite selecionar mic ou system audio source
- **D-32:** System audio usa `parec` (PipeWire/PulseAudio) no Linux, `WASAPI loopback` no Windows, `sox/ffmpeg` no macOS

### Architecture: Electron Orchestrator + Python Subprocess
- **D-33:** Electron Main process (TypeScript) é o orchestrator — controla o lifecycle do Python subprocess
- **D-34:** Comunicação Electron ↔ Python via stdin/stdout JSON commands (já usado para server spawn)
- **D-35:** Python subprocess único (`audio_engine.py`) que faz both recording + transcription
- **D-36:** AudioRecorder em Python faz captura real de áudio (mic e system) — não reescrever em Node

### Audio Flow
- **D-37:** `start_recording` → IPC command do renderer para Electron main → JSON para Python subprocess
- **D-38:** RMS events fluem via stdout JSON → Electron main → IPC → renderer → AudioVisualizer (real-time)
- **D-39:** `stop_recording` → WAV path enviado ao `POST /transcribe` (FastAPI em outro processo na porta 18763)
- **D-40:** SSE response → transcribe chunks → IPC → renderer → QuillJS editor

### Import Audio
- **D-41:** Formatos suportados: MP3 e WAV
- **D-42:** File picker no renderer → envia ficheiro direto para POST /transcribe via fetch (renderer → localhost:18763)

### Button Layout
- **D-43:** TopBar: `ProviderToggle | [spacer] | NetworkStatus | LanguageToggle | ImportAudio | History`
- **D-44:** BottomBar: `Timer | Visualizer | [RecordButton+MicSystemToggle] | CancelButton | Copy | Reset`

### VU Meter Real-Time
- **D-45:** RMS enviado do Python subprocess para Electron main via stdout JSON line (`{"rms": 0.75}`)
- **D-46:** Electron main faz `webContents.send('rms-update', value)` para o renderer

### Frontend ↔ Backend
- **D-47:** FastAPI SSE server corre em processo separado (spawned by Electron na porta 18763)
- **D-48:** Renderer usa `fetch` direto para `http://localhost:18763/transcribe` (FastAPI CORS configurado para permitir)

### Python Subprocess Lifecycle
- **D-49:** Electron faz spawn do `audio_engine.py` ao iniciar, mata ao fechar window
- **D-50:** Se Python morrer unexpectedmente, Electron detecta e reinicia

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Electron Side
- `electron/src/main/index.ts` — Electron main process; audio_engine spawn/kill/lifecycle
- `electron/src/preload/index.ts` — IPC bridge; precisa de novos canais: `rms-update`, `audio-command`
- `electron/src/renderer/composables/useTranscriptionState.ts` — State machine; precisa de integração real com backend
- `electron/src/renderer/components/bottom/AudioVisualizer.vue` — VU meter; recebe `is-active` + needs RMS value input
- `electron/src/renderer/components/bottom/RecordButton.vue` — needs mic/system toggle integrado
- `electron/src/renderer/components/bottom/BottomActionBar.vue` — layout com Copy | Reset à direita
- `electron/src/renderer/components/topbar/TopActionButtons.vue` — reordenar: Copy+History saem, ImportAudio entra
- `electron/src/renderer/components/topbar/LanguageToggle.vue` — não muda

### Python Side
- `app/audio_recorder.py` — AudioRecorder com `start_recording(mode)` e `stop_recording()` returning WAV path; já tem mic + system (parec)
- `app/server.py` — FastAPI POST /transcribe (multipart audio) + SSE streaming

### Integration
- `electron/src/renderer/composables/useTabs.ts` — `updateContent(tabId, text)` para insert transcription
- `app/transcriber.py` — `Transcriber.transcribe()` com `on_chunk` callback para streaming

</canonical_refs>

<codebase>
## Existing Code Insights

### Reusable Assets
- `AudioRecorder.start_recording(mode="mic"|"system")` — already implemented via `parec` for PipeWire/PulseAudio system audio capture
- `AudioRecorder.stop_recording()` — returns `Path` to temp WAV file
- `app/server.py` POST /transcribe — already accepts multipart audio upload and streams transcription via SSE
- `AudioVisualizer` component — exists and receives `is-active` prop (currently hardcoded to RECORDING state)
- `RecordButton` — has 3 states (IDLE/RECORDING/TRANSCRIBING) already

### Established Patterns
- `useTranscriptionState` composable manages state transitions (IDLE/RECORDING/TRANSCRIBING)
- IPC via `contextBridge` and `ipcRenderer.invoke` for secure main↔renderer communication
- SSE streaming with `event: chunk` and `data: [DONE]/[ERROR]` protocol from Phase 2
- Electron main process spawning Python subprocess via `spawn()` with stdout pipe

### Integration Points
- `electron/src/main/index.ts` — where the FastAPI server process is spawned as child; audio_engine would be another subprocess spawned here
- `useTranscriptionState` — currently mocked transcription; needs real backend call
- AudioVisualizer needs real-time RMS from recording to update during RECORDING state

</codebase>

<specifics>
## Specific Ideas

### Mic/System Toggle
- Small icon button next to RecordButton: shows mic icon or speaker icon
- Click cycles: mic → system → mic
- Tooltip shows current source

### Audio Engine Protocol (stdout JSON)
```json
// Python → Electron (RMS events during recording)
{"type": "rms", "value": 0.75}

// Python → Electron (recording started/stopped)
{"type": "status", "recording": true, "mode": "mic"}
{"type": "status", "recording": false, "wav_path": "/tmp/xxx.wav"}

// Electron → Python (commands)
{"action": "start", "mode": "mic"}
{"action": "stop"}
```

### Import Audio Flow
1. Renderer shows file picker (accept: .mp3, .wav)
2. File sent via `fetch('http://localhost:18763/transcribe', {method: 'POST', body: FormData})`
3. SSE response parsed and chunks inserted into editor via `useTabs().updateContent()`

</specifics>

<deferred>
## Deferred Ideas

- Whisper per-segment chunked streaming (Phase 2 deferred — returns all at once today)
- History panel (Phase 1 gap — not yet implemented)
- Real-time SSE chunk insertion into QuillJS editor (Phase 2 SSE client side — will be done in this phase)
- Cross-platform system audio (Windows WASAPI, macOS) — implement per-platform detection

</deferred>
