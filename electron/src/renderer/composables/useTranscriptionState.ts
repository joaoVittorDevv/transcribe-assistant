import { ref, computed, onUnmounted, watch } from 'vue';
import { useTabs } from './useTabs';
import { useDefaultPrompt } from './useDefaultPrompt';
import { useProvider } from './useProvider';
import { useTranscriptionProgress, PROGRESS_STEPS, type ProgressPhase } from './useTranscriptionProgress';
import type { ElectronAPI } from '../types/global';
import { useSocket } from './useSocket';
import { useEditor } from './useEditor';
import { useStreamingTranscription } from './useStreamingTranscription';

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
export function useTranscriptionState() {
  const { resetInsertionPoint } = useEditor();
  const { activeTabId } = useTabs();
  const api = window.electronAPI as ElectronAPI;
  const { promptData } = useDefaultPrompt();
  const { selectedProvider } = useProvider();
  
  const { isStreamingActive, isRecordingStream, onFinal } = useStreamingTranscription();

  // Watch for changes in streaming state to reset UI state on finish/error
  watch(isRecordingStream, (recording) => {
    if (!recording && isStreamingActive.value && state.value !== 'IDLE') {
      state.value = 'IDLE';
      elapsedSeconds.value = 0;
      if (timerInterval) { clearInterval(timerInterval); timerInterval = null; }
    }
  });

  onFinal(() => {
    state.value = 'IDLE';
    elapsedSeconds.value = 0;
    if (timerInterval) { clearInterval(timerInterval); timerInterval = null; }
  });

  // Socket.IO event listeners setup (run once)
  let socketListenersInitialized = false;

  function initSocketListeners() {
    if (socketListenersInitialized) return;
    const { socket } = useSocket();
    const { insertTextWithAck, resetInsertionPoint } = useEditor();
    const { setPhase, reset: resetProgress } = useTranscriptionProgress();

    if (!socket.value) return;

    socket.value.on('transcription:chunk', async (payload, callback) => {
      if (payload.sessionId !== sessionId.value) {
        callback({ status: 'ignored' });
        return;
      }
      try {
        const { activeTabId } = useTabs();
        await insertTextWithAck(payload.text, activeTabId.value);
        callback({ status: 'ok' });
      } catch (e) {
        console.error('[Socket.IO] Error inserting text:', e);
        // Do not ack or maybe ack with error to trigger retry? We'll ack to keep it flowing.
        callback({ status: 'error' });
      }
    });

    socket.value.on('transcription:status', (payload) => {
      if (payload.sessionId !== sessionId.value) return;
      const phase = payload.phase as ProgressPhase;
      const message = payload.message;
      if (phase === 'error') {
        setPhase('error', message || 'Erro na transcrição');
      } else {
        const knownPhases = new Set(PROGRESS_STEPS.map((s) => s.id));
        if (knownPhases.has(phase)) {
          setPhase(phase, message);
        } else if ((phase as string) === 'cancelled') {
           // handled in handleCancel
        }
      }
    });

    socket.value.on('transcription:error', (payload) => {
      if (payload.sessionId !== sessionId.value) return;
      setPhase('error', payload.message || 'Erro desconhecido');
      api.updateAudioState('error');
    });

    socket.value.on('transcription:done', (payload) => {
      if (payload.sessionId !== sessionId.value) return;
      setPhase('done');
      setTimeout(() => {
        resetProgress();
        state.value = 'IDLE';
        elapsedSeconds.value = 0;
        sessionId.value = null;
      }, 2000);
    });

    socketListenersInitialized = true;
  }

  // NOVO: Transcrição dual — envia dois arquivos separadamente
  async function transcribeDual(paths: { mic: string | null; sys: string | null }) {
    let micPath = paths.mic;
    let sysPath = paths.sys;
    // Capture target tab so streaming goes to the correct tab even if user switches
    const targetTabId = activeTabId.value;
    // Reset editor's tracked insertion point so it re-captures cursor on first chunk
    resetInsertionPoint();
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

      const { socket } = useSocket();
      initSocketListeners();
      
      if (socket.value) {
        formData.append('X-Socket-ID', socket.value.id || '');
      }

      const response = await fetch(`http://localhost:18763/transcribe/dual`, {
        method: 'POST',
        body: formData,
        signal: abortController.signal,
        headers: socket.value?.id ? { 'X-Socket-ID': socket.value.id } : {}
      });

      if (!response.ok) {
        console.error('[transcription] dual HTTP error:', response.status, response.statusText);
        setPhase('error', `Erro HTTP ${response.status}: ${response.statusText}`);
        return;
      }

      const resData = await response.json();
      sessionId.value = resData.sessionId;

      // Keep source recordings in Vault. They are the durable recovery copy if
      // the provider, server, or UI fails after accepting the request.

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
    resetInsertionPoint();
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

      const { socket } = useSocket();
      initSocketListeners();

      const response = await fetch(`http://localhost:18763/transcribe`, {
        method: 'POST',
        body: formData,
        signal: abortController.signal,
        headers: socket.value?.id ? { 'X-Socket-ID': socket.value.id } : {}
      });

      if (!response.ok) {
        console.error('[transcription] HTTP error:', response.status, response.statusText);
        setPhase('error', `Erro HTTP ${response.status}: ${response.statusText}`);
        return;
      }

      const resData = await response.json();
      sessionId.value = resData.sessionId;

      // Keep the source recording in Vault until retention cleanup explicitly
      // removes it. HTTP acceptance does not mean transcription succeeded.

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

    const { isStreamingActive, startStreaming } = useStreamingTranscription();
    if (isStreamingActive.value) {
      startStreaming(currentMode);
    } else {
      api.audioCommand({ action: 'start', mode: currentMode });
    }

    const started = await recordingStarted;
    if (!started) {
      console.error('[transcription] audio engine failed to start recording');
      return;
    }

    state.value = 'RECORDING';
    timerInterval = setInterval(() => elapsedSeconds.value++, 1000);
  }

  async function stopAndTranscribe() {
    const { isStreamingActive, stopStreaming } = useStreamingTranscription();

    if (isStreamingActive.value) {
      state.value = 'TRANSCRIBING';
      if (timerInterval) { clearInterval(timerInterval); timerInterval = null; }
      stopStreaming();
      return;
    }

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
    const { isStreamingActive, cancelStreaming } = useStreamingTranscription();

    if (isStreamingActive.value) {
      if (timerInterval) { clearInterval(timerInterval); timerInterval = null; }
      cancelStreaming();
      state.value = 'IDLE';
      elapsedSeconds.value = 0;
      rmsValue.value = 0;
      resetProgress();
      return;
    }

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
      abortController?.abort();
      const { socket } = useSocket();
      if (sessionId.value && socket.value) {
        socket.value.emit('transcription:cancel', { sessionId: sessionId.value });
        // Also fire the HTTP DELETE just in case as fallback (idempotent)
        fetch(`http://localhost:18763/transcribe/${sessionId.value}`, {
          method: 'DELETE',
        }).catch(() => {});
      }
      // Stop WAV polling if still waiting for engine
      if (wavCheckInterval) {
        clearInterval(wavCheckInterval);
        wavCheckInterval = null;
      }
      // Audio files stay in Vault/recordings — cancelling the job must never
      // delete the recording itself. Retention handles cleanup later.
      pendingWavPaths = null;
      pendingWavPath = null;
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
    resetInsertionPoint();
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

      const { socket } = useSocket();
      initSocketListeners();

      const response = await fetch('http://localhost:18763/transcribe', {
        method: 'POST',
        body: formData,
        signal: abortController.signal,
        headers: socket.value?.id ? { 'X-Socket-ID': socket.value.id } : {}
      });

      if (!response.ok) {
        setPhase('error', `Erro HTTP ${response.status}: ${response.statusText}`);
        return;
      }

      const resData = await response.json();
      sessionId.value = resData.sessionId;

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
