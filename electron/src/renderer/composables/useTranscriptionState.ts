import { ref, computed, onUnmounted, watch } from 'vue';
import { useTabs } from './useTabs';
import { useDefaultPrompt } from './useDefaultPrompt';
import { useProvider } from './useProvider';
import { useTranscriptionProgress, PROGRESS_STEPS, type ProgressPhase } from './useTranscriptionProgress';
import type { ElectronAPI } from '../types/global';

export type TranscriptionState = 'IDLE' | 'RECORDING' | 'TRANSCRIBING';

const state = ref<TranscriptionState>('IDLE');
const elapsedSeconds = ref(0);
const rmsValue = ref(0);
let currentMode: 'mic' | 'system' | 'dual' = 'mic';
let timerInterval: ReturnType<typeof setInterval> | null = null;
let cleanupRms: (() => void) | null = null;
let cleanupStatus: (() => void) | null = null;
// Captured WAV paths for dual mode
let pendingWavPaths: { mic: string | null; sys: string | null; error?: string } | null = null;
// Backward-compatible single path (non-dual modes)
let pendingWavPath: string | null = null;
// Resolve function for start-recording confirmation (Bug 1a fix)
let recordingStartResolve: ((value: boolean) => void) | null = null;
// AbortController for cancelling in-flight transcription fetch
let abortController: AbortController | null = null;
// Session ID captured from SSE response headers, used for server-side cancel
const sessionId = ref<string | null>(null);

// Tracks if WAV generation timeout has expired (race condition fix)
let wavGenerationTimedOut = false;
// Interval ID for WAV polling — cleared on cancel to prevent stale triggers
let wavCheckInterval: ReturnType<typeof setInterval> | null = null;

// ---------------------------------------------------------------------------
// Shared SSE stream consumer
// ---------------------------------------------------------------------------
// Extracted from the triplicated parser logic in transcribeFile, transcribeDual,
// and importAndTranscribe to ensure bug fixes apply consistently across all flows.

interface SSEStreamOptions {
  reader: ReadableStreamDefaultReader<Uint8Array>;
  targetTabId: string;
  setPhase: (phase: ProgressPhase, message?: string) => void;
  resetProgress: () => void;
  logPrefix: string;
  onDone?: () => void;
}

async function consumeSSEStream(options: SSEStreamOptions): Promise<void> {
  const { reader, targetTabId, setPhase, resetProgress, logPrefix, onDone } = options;
  const api = window.electronAPI as ElectronAPI;
  const decoder = new TextDecoder();
  let buffer = '';
  let chunksReceived = 0;
  let eventType = '';
  const dataLines: string[] = [];

  // Flush an accumulated SSE event.
  // Returns 'return' if caller should exit.
  const flushEvent = async (type: string, data: string): Promise<'continue' | 'return'> => {
    if (type === 'status') {
      try {
        const statusPayload = JSON.parse(data);
        const phase = statusPayload.phase as ProgressPhase;
        const message = statusPayload.message as string | undefined;
        // Handle error phase from server (not in PROGRESS_STEPS — it's a terminal state)
        if (phase === 'error') {
          setPhase('error', message || 'Erro na transcrição');
          return 'continue';
        }
        // Only dispatch known phases to avoid progress glitches
        const knownPhases = new Set(PROGRESS_STEPS.map((s) => s.id));
        if (phase && knownPhases.has(phase)) {
          setPhase(phase, message);
          console.debug(`[Transcription] ${logPrefix} status:`, phase, message ?? '');
        } else if (phase) {
          console.debug(`[Transcription] ${logPrefix} ignoring unknown phase:`, phase);
        }
      } catch (e) {
        console.warn(`[Transcription] ${logPrefix} failed to parse status event:`, data);
      }
      return 'continue';
    }
    // 'chunk' event (or default) — handle [DONE], [ERROR], or text
    if (data === '[DONE]') {
      console.log(`[Transcription] ${logPrefix} completed —`, chunksReceived, 'chunks received');
      setPhase('done');
      // Brief delay to show done state before resetting
      setTimeout(() => {
        resetProgress();
        state.value = 'IDLE';
        elapsedSeconds.value = 0;
        sessionId.value = null;
      }, 2000);
      onDone?.();
      return 'return';
    }
    if (data.startsWith('[ERROR]')) {
      console.error(`[transcription] ${logPrefix} error:`, data);
      const errorMsg = data.slice(7).trim() || 'Erro desconhecido na transcrição';
      setPhase('error' as ProgressPhase, errorMsg);
      api.updateAudioState('error');
      return 'return';
    }
    // Server sends raw text chunks (not JSON) — insert directly
    chunksReceived++;
    console.debug(`[Transcription] ${logPrefix} chunk #${chunksReceived}:`, data.length, 'chars');
    await api.insertTextAtCursor(data, targetTabId);
    return 'continue';
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';
    for (const line of lines) {
      // Empty line = SSE event boundary → flush accumulated event
      if (line === '' || line === '\r') {
        if (dataLines.length > 0) {
          const dataStr = dataLines.join('\n');
          const result = await flushEvent(eventType, dataStr);
          eventType = '';
          dataLines.length = 0;
          if (result === 'return') return;
        }
        continue;
      }
      // Accumulate SSE fields
      if (line.startsWith('event:')) {
        eventType = line.slice(6).trim();
      } else if (line.startsWith('data:')) {
        let dataContent = line.slice(5);
        if (dataContent.startsWith(' ')) dataContent = dataContent.slice(1);
        dataLines.push(dataContent);
      }
      // Lines not starting with event: or data: are SSE comments — ignored
    }
  }
  // Flush last event if stream ended without trailing empty line
  if (dataLines.length > 0) {
    const dataStr = dataLines.join('\n');
    const result = await flushEvent(eventType, dataStr);
    if (result === 'return') return;
  }
}

export function useTranscriptionState() {
  const { activeTabId } = useTabs();
  const api = window.electronAPI as ElectronAPI;
  const { promptData } = useDefaultPrompt();
  const { selectedProvider } = useProvider();

  // NOVO: Transcrição dual — envia dois arquivos separadamente
  async function transcribeDual(paths: { mic: string | null; sys: string | null }) {
    let micPath = paths.mic;
    let sysPath = paths.sys;
    // Capture target tab so streaming goes to the correct tab even if user switches
    const targetTabId = activeTabId.value;
    // Reset editor's tracked insertion point so it re-captures cursor on first chunk
    api.resetInsertionPoint();
    // Create new AbortController for this transcription
    abortController = new AbortController();
    sessionId.value = null;
    const { setPhase, reset: resetProgress } = useTranscriptionProgress();

    // Validate paths
    if (!micPath || !sysPath) {
      const missing = !micPath && !sysPath ? 'ambos' : !micPath ? 'microfone' : 'sistema';
      setPhase('error', `Erro: Falha ao capturar áudio de ${missing}.`);
      return;
    }

    try {
      // Read both audio files in parallel
      const [micBuffer, sysBuffer] = await Promise.all([
        api.readFile(micPath),
        api.readFile(sysPath),
      ]);

      if (!micBuffer || !sysBuffer) {
        throw new Error('Falha ao ler arquivos de áudio');
      }

      const formData = new FormData();
      formData.append('mic_audio', new Blob([micBuffer], { type: 'audio/wav' }), 'mic.wav');
      formData.append('sys_audio', new Blob([sysBuffer], { type: 'audio/wav' }), 'sys.wav');
      formData.append('prompt_text', promptData.value.texto_prompt);
      formData.append('keywords', promptData.value.keywords.join(', '));
      formData.append('mode', 'gemini'); // Dual mode always uses Gemini
      formData.append('source', 'dual');

      console.log('[Transcription] dual mode: sending mic.wav + sys.wav to /transcribe/dual');

      const response = await fetch(`http://localhost:18763/transcribe/dual`, {
        method: 'POST',
        body: formData,
        signal: abortController.signal,
      });

      // Capture session ID from response headers
      const sid = response.headers.get('X-Session-ID');
      if (sid) sessionId.value = sid;

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');

      await consumeSSEStream({
        reader,
        targetTabId,
        setPhase,
        resetProgress,
        logPrefix: 'dual',
        onDone: () => {
          // Clean up dual audio files on success
          if (micPath) api.deleteFile(micPath).catch(() => {});
          if (sysPath) api.deleteFile(sysPath).catch(() => {});
        },
      });

      if (!response.ok) {
        console.error('[transcription] dual HTTP error:', response.status, response.statusText);
        setPhase('error', `Erro HTTP ${response.status}: ${response.statusText}`);
        return;
      }
    } catch (err: any) {
      if (err?.name === 'AbortError') {
        console.log('[transcription] dual fetch aborted by user');
        return;
      }
      console.error('[transcription] dual error:', err);
      const errMsg = err?.message || 'Erro desconhecido';
      // Preserve audio paths in error message for debugging
      setPhase('error', `Erro na transcrição: ${errMsg}\n\nÁudios preservados em:\n• Mic: ${micPath}\n• Sys: ${sysPath}`);
      api.updateAudioState('error');
      return;
    }
    setPhase('error', 'Conexão perdida com o servidor de transcrição.');
  }

  async function transcribeFile(wavPath: string) {
    // Capture target tab so streaming goes to the correct tab even if user switches
    const targetTabId = activeTabId.value;
    // Reset editor's tracked insertion point so it re-captures cursor on first chunk
    api.resetInsertionPoint();
    // Create new AbortController for this transcription
    abortController = new AbortController();
    sessionId.value = null;
    const { setPhase, reset: resetProgress } = useTranscriptionProgress();
    try {
      const arrayBuffer = await api.readFile(wavPath);
      if (!arrayBuffer) throw new Error('Failed to read audio file');

      const formData = new FormData();
      formData.append('audio', new Blob([arrayBuffer], { type: 'audio/wav' }), 'audio.wav');
      formData.append('prompt_text', promptData.value.texto_prompt);
      formData.append('keywords', promptData.value.keywords.join(', '));
      // Determine transcription mode based on audio source and provider selection
      let transcriptionMode: string;
      if (currentMode === 'system') {
        // System audio always uses Google Gemini
        transcriptionMode = 'gemini';
      } else if (currentMode === 'dual') {
        // Dual mode uses Gemini for diarization (speaker identification)
        transcriptionMode = 'gemini';
      } else {
        // Mic audio respects user provider selection
        switch (selectedProvider.value) {
          case 'google':
            transcriptionMode = 'gemini';
            break;
          case 'groq':
            transcriptionMode = 'groq';
            break;
          case 'auto':
          default:
            transcriptionMode = 'auto';
            break;
        }
      }
      console.log('[Transcription] mode:', transcriptionMode, '| source:', currentMode, '| provider:', selectedProvider.value);
      formData.append('mode', transcriptionMode);
      formData.append('source', currentMode);

      // Dual mode uses Gemini for diarization — log hint for transparency
      if (currentMode === 'dual') {
        console.log('[Transcription] dual mode: forcing Gemini for speaker diarization');
      }

      const response = await fetch(`http://localhost:18763/transcribe`, {
        method: 'POST',
        body: formData,
        signal: abortController.signal,
      });

      // Capture session ID from response headers for server-side cancel
      const sid = response.headers.get('X-Session-ID');
      if (sid) sessionId.value = sid;

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');

      await consumeSSEStream({
        reader,
        targetTabId,
        setPhase,
        resetProgress,
        logPrefix: 'single',
        onDone: () => {
          // Clean up Vault file on successful transcription
          if (wavPath) {
            api.deleteFile(wavPath).catch(() => {});
          }
        },
      });

      if (!response.ok) {
        console.error('[transcription] HTTP error:', response.status, response.statusText);
        setPhase('error', `Erro HTTP ${response.status}: ${response.statusText}`);
        return;
      }
    } catch (err: any) {
      // AbortError is expected when user cancels — not an error
      if (err?.name === 'AbortError') {
        console.log('[transcription] fetch aborted by user');
        return;
      }
      console.error('[transcription] error:', err);
      setPhase('error', err?.message || 'Erro durante a transcrição');
      api.updateAudioState('error');
      return;
    }
    // Only reached if stream ends without [DONE] or [ERROR] — show error, don't auto-close
    setPhase('error', 'Conexão perdida com o servidor de transcrição.');
  }

  async function startRecording() {
    pendingWavPath = null;
    pendingWavPaths = null;
    elapsedSeconds.value = 0;

    // Bug 1a fix: wait for audio engine to confirm recording started
    // before setting state to RECORDING. This prevents the user from
    // speaking before the engine is actually capturing audio.
    const recordingStarted = new Promise<boolean>((resolve) => {
      recordingStartResolve = resolve;
      // Safety timeout: if no confirmation within 5s, abort
      setTimeout(() => {
        if (recordingStartResolve) {
          recordingStartResolve = null;
          resolve(false);
        }
      }, 5000);
    });

    api.audioCommand({ action: 'start', mode: currentMode });

    const started = await recordingStarted;
    if (!started) {
      console.error('[transcription] audio engine failed to start recording');
      return;
    }

    state.value = 'RECORDING';
    timerInterval = setInterval(() => elapsedSeconds.value++, 1000);
  }

  async function stopAndTranscribe() {
    state.value = 'TRANSCRIBING';
    if (timerInterval) { clearInterval(timerInterval); timerInterval = null; }
    wavGenerationTimedOut = false;

    api.audioCommand({ action: 'stop' });

    const { setPhase, statusMessage } = useTranscriptionProgress();

    let phaseTwoTimeout: ReturnType<typeof setTimeout> | null = null;
    let phaseThreeTimeout: ReturnType<typeof setTimeout> | null = null;

    // Poll every 50ms for the WAV path(s).
    // On arrival: cancel all timeouts, clear status, start transcription.
    wavCheckInterval = setInterval(() => {
      // Dual mode: two paths available
      if (pendingWavPaths && !wavGenerationTimedOut) {
        clearInterval(wavCheckInterval!);
        wavCheckInterval = null;
        if (phaseTwoTimeout) clearTimeout(phaseTwoTimeout);
        if (phaseThreeTimeout) clearTimeout(phaseThreeTimeout);
        statusMessage.value = '';
        transcribeDual(pendingWavPaths);
        pendingWavPaths = null;
        return;
      }
      // Single mode (backward compatible)
      if (pendingWavPath && !wavGenerationTimedOut) {
        clearInterval(wavCheckInterval!);
        wavCheckInterval = null;
        if (phaseTwoTimeout) clearTimeout(phaseTwoTimeout);
        if (phaseThreeTimeout) clearTimeout(phaseThreeTimeout);
        statusMessage.value = '';
        transcribeFile(pendingWavPath);
        pendingWavPath = null;
      }
    }, 50);

    // Phase 2 (5 s): gravação longa — mostra feedback mas continua esperando
    phaseTwoTimeout = setTimeout(() => {
      if (state.value === 'TRANSCRIBING' && !pendingWavPaths && !pendingWavPath) {
        statusMessage.value = 'Finalizando gravação longa…';
        console.log('[transcription] WAV generation taking longer than 5s — still waiting');
      }
    }, 5000);

    // Phase 3 (30 s): erro real — engine não respondeu a tempo
    phaseThreeTimeout = setTimeout(() => {
      if (wavCheckInterval) {
        clearInterval(wavCheckInterval);
        wavCheckInterval = null;
      }
      if (phaseTwoTimeout) clearTimeout(phaseTwoTimeout);
      if (state.value === 'TRANSCRIBING') {
        wavGenerationTimedOut = true;
        setPhase('error', 'Timeout: gravação não finalizou a tempo. Tente novamente.');
        pendingWavPath = null;
        pendingWavPaths = null;
      }
    }, 30000);
  }

  async function handleRecordClick() {
    if (state.value === 'IDLE') {
      await startRecording();
    } else if (state.value === 'RECORDING') {
      await stopAndTranscribe();
    }
  }

  function handleCancel() {
    const { reset: resetProgress } = useTranscriptionProgress();
    if (state.value === 'RECORDING') {
      // Cancel recording: discard audio via 'cancel' action (no WAV saved)
      if (timerInterval) { clearInterval(timerInterval); timerInterval = null; }
      api.audioCommand({ action: 'cancel' });
      state.value = 'IDLE';
      elapsedSeconds.value = 0;
      rmsValue.value = 0;
      pendingWavPath = null;
      pendingWavPaths = null;
      resetProgress();
    } else if (state.value === 'TRANSCRIBING') {
      // Cancel transcription: abort in-flight fetch + notify server
      abortController?.abort();
      if (sessionId.value) {
        fetch(`http://localhost:18763/transcribe/${sessionId.value}`, {
          method: 'DELETE',
        }).catch(() => {});
      }
      // Stop WAV polling if still waiting for engine
      if (wavCheckInterval) {
        clearInterval(wavCheckInterval);
        wavCheckInterval = null;
      }
      // Clean up Vault WAV file if we have one
      if (pendingWavPaths) {
        if (pendingWavPaths.mic) api.deleteFile(pendingWavPaths.mic).catch(() => {});
        if (pendingWavPaths.sys) api.deleteFile(pendingWavPaths.sys).catch(() => {});
        pendingWavPaths = null;
      } else if (pendingWavPath) {
        api.deleteFile(pendingWavPath).catch(() => {});
        pendingWavPath = null;
      }
      state.value = 'IDLE';
      elapsedSeconds.value = 0;
      sessionId.value = null;
      resetProgress();
    }
  }

  function setMode(mode: 'mic' | 'system' | 'dual') {
    currentMode = mode;
  }

  cleanupRms = api.onRmsUpdate((value: number) => {
    rmsValue.value = value;
  });

  cleanupStatus = api.onAudioStatus((status) => {
    // Handle engine startup or recording failure (e.g. audio device busy)
    if (!status.recording && status.error) {
      if (recordingStartResolve) {
        recordingStartResolve(false);
        recordingStartResolve = null;
      }
      state.value = 'IDLE';
      elapsedSeconds.value = 0;
      rmsValue.value = 0;
      if (timerInterval) {
        clearInterval(timerInterval);
        timerInterval = null;
      }
      const { setPhase } = useTranscriptionProgress();
      setPhase('error', `Erro no dispositivo de áudio: ${status.error}`);
      api.updateAudioState('error');
      return;
    }

    // Bug 1a fix: resolve start-recording promise when engine confirms
    if (status.recording && recordingStartResolve) {
      recordingStartResolve(true);
      recordingStartResolve = null;
    }
    // Only process wav paths if timeout hasn't expired (race condition fix)
    if (!status.recording && !wavGenerationTimedOut) {
      if (status.dual) {
        // Dual mode: two separate paths
        pendingWavPaths = {
          mic: status.mic_wav_path ?? null,
          sys: status.sys_wav_path ?? null,
          error: status.error,
        };
        pendingWavPath = null;
      } else if (status.wav_path) {
        // Single mode: backward compatible
        pendingWavPath = status.wav_path;
        pendingWavPaths = null;
      }
    }
  });

  // Watch state changes to update Tray icon via IPC
  watch(state, (newState) => {
    api.updateAudioState(newState.toLowerCase() as 'idle' | 'recording' | 'transcribing');
  });

  // Listen for stop from system tray
  const cleanupStopFromTray = api.onStopRecordingFromTray(() => {
    if (state.value === 'RECORDING') {
      stopAndTranscribe();
    }
  });
 
  onUnmounted(() => {
    if (timerInterval) clearInterval(timerInterval);
    abortController?.abort();
    cleanupRms?.();
    cleanupStatus?.();
    cleanupStopFromTray?.();
  });

  // Import audio file and transcribe with unified progress bar
  async function importAndTranscribe() {
    if (state.value !== 'IDLE') return;

    const filePath = await api.openFilePicker(['mp3', 'wav']);
    if (!filePath) return;

    const arrayBuffer = await api.readFile(filePath);
    if (!arrayBuffer) return;

    // Capture target tab before async work begins
    const targetTabId = activeTabId.value;

    state.value = 'TRANSCRIBING';
    api.resetInsertionPoint();
    abortController = new AbortController();
    sessionId.value = null;
    const { setPhase, reset: resetProgress } = useTranscriptionProgress();

    try {
      const ext = filePath.split('.').pop()?.toLowerCase() ?? 'wav';
      const mimeType = ext === 'mp3' ? 'audio/mpeg' : 'audio/wav';
      const blob = new Blob([arrayBuffer], { type: mimeType });
      const formData = new FormData();
      formData.append('audio', blob, filePath.split('/').pop() ?? 'audio');
      formData.append('prompt_text', promptData.value.texto_prompt);
      formData.append('keywords', promptData.value.keywords.join(', '));
      // Imported files always use Google Gemini
      formData.append('mode', 'gemini');
      formData.append('source', 'import');

      const response = await fetch('http://localhost:18763/transcribe', {
        method: 'POST',
        body: formData,
        signal: abortController.signal,
      });

      // Capture session ID from response headers
      const sid = response.headers.get('X-Session-ID');
      if (sid) sessionId.value = sid;

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');

      await consumeSSEStream({
        reader,
        targetTabId,
        setPhase,
        resetProgress,
        logPrefix: 'import',
      });

      if (!response.ok) {
        setPhase('error', `Erro HTTP ${response.status}: ${response.statusText}`);
        return;
      }
    } catch (err: any) {
      if (err?.name === 'AbortError') {
        console.log('[transcription] import fetch aborted by user');
        return;
      }
      console.error('[transcription] import error:', err);
      setPhase('error', err?.message || 'Erro durante a transcrição');
      api.updateAudioState('error');
      return;
    }
    setPhase('error', 'Conexão perdida com o servidor de transcrição.');
  }

  return {
    transcriptionState: state,
    elapsedSeconds,
    rmsValue,
    currentMode,
    isShowingCancel: computed(() => state.value === 'RECORDING' || state.value === 'TRANSCRIBING'),
    handleRecordClick,
    handleCancel,
    setMode,
    importAndTranscribe,
  };
}
