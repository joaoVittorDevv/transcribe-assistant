import { ref, computed, onUnmounted } from 'vue';
import { useTabs } from './useTabs';
import { useDefaultPrompt } from './useDefaultPrompt';
import { useProvider } from './useProvider';
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

let quillCursorIndex = 0;

export function useTranscriptionState() {
  const { activeTabId, updateContent } = useTabs();
  const api = window.electronAPI as ElectronAPI;
  const { promptData } = useDefaultPrompt();
  const { selectedProvider } = useProvider();

  async function transcribeFile(wavPath: string) {
    let accumulated = '';
    quillCursorIndex = 0;
    // Create new AbortController for this transcription
    abortController = new AbortController();
    sessionId.value = null;
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

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';
        for (const line of lines) {
          if (!line.startsWith('data:')) continue;
          // Extract payload preserving trailing whitespace (backend controls word spacing)
          let dataStr = line.slice(5);
          if (dataStr.startsWith(' ')) dataStr = dataStr.slice(1);
          if (dataStr === '[DONE]') {
            console.log('[Transcription] completed —', chunksReceived, 'chunks received');
            state.value = 'IDLE';
            elapsedSeconds.value = 0;
            sessionId.value = null;
            // Clean up Vault file on successful transcription
            if (wavPath) {
              api.deleteFile(wavPath).catch(() => {});
            }
            return;
          }
          if (dataStr.startsWith('[ERROR]')) {
            console.error('[transcription]', dataStr);
            state.value = 'IDLE';
            elapsedSeconds.value = 0;
            sessionId.value = null;
            return;
          }
          // Server sends raw text chunks (not JSON) — insert directly
          chunksReceived++;
          console.debug('[Transcription] chunk #' + chunksReceived + ':', dataStr.length, 'chars');
          await api.insertTextAtCursor(dataStr);
        }
      }

      if (!response.ok) {
        console.error('[transcription] HTTP error:', response.status, response.statusText);
        state.value = 'IDLE';
        elapsedSeconds.value = 0;
        sessionId.value = null;
        return;
      }
    } catch (err: any) {
      // AbortError is expected when user cancels — not an error
      if (err?.name === 'AbortError') {
        console.log('[transcription] fetch aborted by user');
        return;
      }
      console.error('[transcription] error:', err);
    }
    state.value = 'IDLE';
    elapsedSeconds.value = 0;
    sessionId.value = null;
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

    api.audioCommand({ action: 'stop' });

    // Wait for wav_path to arrive via onAudioStatus, then transcribe
    const checkPath = setInterval(() => {
      if (pendingWavPath) {
        clearInterval(checkPath);
        transcribeFile(pendingWavPath);
        pendingWavPath = null;
      }
    }, 50);

    // Safety timeout: if no wav_path within 5s, give up
    setTimeout(() => {
      clearInterval(checkPath);
      if (state.value === 'TRANSCRIBING') {
        state.value = 'IDLE';
        elapsedSeconds.value = 0;
        pendingWavPath = null;
      }
    }, 5000);
  }

  async function handleRecordClick() {
    if (state.value === 'IDLE') {
      await startRecording();
    } else if (state.value === 'RECORDING') {
      await stopAndTranscribe();
    }
  }

  function handleCancel() {
    if (state.value === 'RECORDING') {
      // Cancel recording: discard audio via 'cancel' action (no WAV saved)
      if (timerInterval) { clearInterval(timerInterval); timerInterval = null; }
      api.audioCommand({ action: 'cancel' });
      state.value = 'IDLE';
      elapsedSeconds.value = 0;
      rmsValue.value = 0;
      pendingWavPath = null;
    } else if (state.value === 'TRANSCRIBING') {
      // Cancel transcription: abort in-flight fetch + notify server
      abortController?.abort();
      if (sessionId.value) {
        fetch(`http://localhost:18763/transcribe/${sessionId.value}`, {
          method: 'DELETE',
        }).catch(() => {});
      }
      // Clean up Vault WAV file if we have one
      if (pendingWavPath) {
        api.deleteFile(pendingWavPath).catch(() => {});
        pendingWavPath = null;
      }
      state.value = 'IDLE';
      elapsedSeconds.value = 0;
      sessionId.value = null;
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
    if (!status.recording && status.wav_path) {
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
