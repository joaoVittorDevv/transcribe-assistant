import { ref, computed, onUnmounted } from 'vue';
import { useTabs } from './useTabs';
import { useDefaultPrompt } from './useDefaultPrompt';
import { useProvider } from './useProvider';
import { useTranscriptionProgress, PROGRESS_STEPS, type ProgressPhase } from './useTranscriptionProgress';
import type { ElectronAPI } from '../types/global';

export type TranscriptionState = 'IDLE' | 'RECORDING' | 'TRANSCRIBING';

const state = ref<TranscriptionState>('IDLE');
const elapsedSeconds = ref(0);
const rmsValue = ref(0);
let currentMode: 'mic' | 'system' = 'mic';
let timerInterval: ReturnType<typeof setInterval> | null = null;
let cleanupRms: (() => void) | null = null;
let cleanupStatus: (() => void) | null = null;
// Captured WAV path returned by audio_engine on stop
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

export function useTranscriptionState() {
  const { activeTabId, updateContent } = useTabs();
  const api = window.electronAPI as ElectronAPI;
  const { promptData } = useDefaultPrompt();
  const { selectedProvider } = useProvider();

  async function transcribeFile(wavPath: string) {
    let accumulated = '';
    // Reset editor’s tracked insertion point so it re-captures cursor on first chunk
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

      const decoder = new TextDecoder();
      let buffer = '';
      let chunksReceived = 0;
      let eventType = '';
      const dataLines: string[] = [];

      // Flush an accumulated SSE event.
      // Returns 'return' if caller should exit transcribeFile.
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
              console.debug('[Transcription] status:', phase, message ?? '');
            } else if (phase) {
              console.debug('[Transcription] ignoring unknown phase:', phase);
            }
          } catch (e) {
            console.warn('[Transcription] failed to parse status event:', data);
          }
          return 'continue';
        }
        // 'chunk' event (or default) — handle [DONE], [ERROR], or text
        if (data === '[DONE]') {
          console.log('[Transcription] completed —', chunksReceived, 'chunks received');
          setPhase('done');
          // Reset editor insertion tracking so next transcription re-captures cursor
          api.resetInsertionPoint();
          // Brief delay to show done state before resetting
          setTimeout(() => {
            resetProgress();
            state.value = 'IDLE';
            elapsedSeconds.value = 0;
            sessionId.value = null;
          }, 2000);
          // Clean up Vault file on successful transcription
          if (wavPath) {
            api.deleteFile(wavPath).catch(() => {});
          }
          return 'return';
        }
        if (data.startsWith('[ERROR]')) {
          console.error('[transcription]', data);
          const errorMsg = data.slice(7).trim() || 'Erro desconhecido na transcrição';
          setPhase('error' as ProgressPhase, errorMsg);
          // Reset editor insertion tracking so next transcription re-captures cursor
          api.resetInsertionPoint();
          // Keep bar visible — user must dismiss manually
          return 'return';
        }
        // Server sends raw text chunks (not JSON) — insert directly
        chunksReceived++;
        console.debug('[Transcription] chunk #' + chunksReceived + ':', data.length, 'chars');
        await api.insertTextAtCursor(data);
        return 'continue';
      }

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
      return;
    }
    // Only reached if stream ends without [DONE] or [ERROR] — show error, don't auto-close
    setPhase('error', 'Conexão perdida com o servidor de transcrição.');
  }

  async function startRecording() {
    pendingWavPath = null;
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

    // Poll every 50ms for the WAV path.
    // On arrival: cancel all timeouts, clear status, start transcription.
    wavCheckInterval = setInterval(() => {
      if (pendingWavPath && !wavGenerationTimedOut) {
        clearInterval(wavCheckInterval!);
        wavCheckInterval = null;
        if (phaseTwoTimeout) clearTimeout(phaseTwoTimeout);
        if (phaseThreeTimeout) clearTimeout(phaseThreeTimeout);
        // Clear any "waiting" message from phase 2
        statusMessage.value = '';
        transcribeFile(pendingWavPath);
        pendingWavPath = null;
      }
    }, 50);

    // Phase 2 (5 s): gravação longa — mostra feedback mas continua esperando
    phaseTwoTimeout = setTimeout(() => {
      if (state.value === 'TRANSCRIBING' && !pendingWavPath) {
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
      if (pendingWavPath) {
        api.deleteFile(pendingWavPath).catch(() => {});
        pendingWavPath = null;
      }
      state.value = 'IDLE';
      elapsedSeconds.value = 0;
      sessionId.value = null;
      resetProgress();
    }
  }

  function setMode(mode: 'mic' | 'system') {
    currentMode = mode;
  }

  cleanupRms = api.onRmsUpdate((value: number) => {
    rmsValue.value = value;
  });

  cleanupStatus = api.onAudioStatus((status) => {
    // Bug 1a fix: resolve start-recording promise when engine confirms
    if (status.recording && recordingStartResolve) {
      recordingStartResolve(true);
      recordingStartResolve = null;
    }
    // Only set wav_path if timeout hasn't expired (race condition fix)
    if (!status.recording && status.wav_path && !wavGenerationTimedOut) {
      pendingWavPath = status.wav_path;
    }
  });

  onUnmounted(() => {
    if (timerInterval) clearInterval(timerInterval);
    abortController?.abort();
    cleanupRms?.();
    cleanupStatus?.();
  });

  return {
    transcriptionState: state,
    elapsedSeconds,
    rmsValue,
    currentMode,
    isShowingCancel: computed(() => state.value === 'RECORDING' || state.value === 'TRANSCRIBING'),
    handleRecordClick,
    handleCancel,
    setMode,
  };
}
