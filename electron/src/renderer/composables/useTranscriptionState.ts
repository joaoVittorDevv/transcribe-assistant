import { ref, onUnmounted } from 'vue';
import { useTabs } from './useTabs';
import { useDefaultPrompt } from './useDefaultPrompt';
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

let quillCursorIndex = 0;

export function useTranscriptionState() {
  const { activeTabId, updateContent } = useTabs();
  const api = window.electronAPI as ElectronAPI;
  const { promptData } = useDefaultPrompt();

  async function transcribeFile(wavPath: string) {
    let accumulated = '';
    quillCursorIndex = 0;
    try {
      const arrayBuffer = await api.readFile(wavPath);
      if (!arrayBuffer) throw new Error('Failed to read audio file');

      const formData = new FormData();
      formData.append('audio', new Blob([arrayBuffer], { type: 'audio/wav' }), 'audio.wav');
      formData.append('prompt_text', promptData.value.texto_prompt);
      formData.append('keywords', promptData.value.keywords.join(', '));

      const response = await fetch(`http://localhost:18763/transcribe`, {
        method: 'POST',
        body: formData,
      });

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');

      const decoder = new TextDecoder();
      let buffer = '';

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
            state.value = 'IDLE';
            elapsedSeconds.value = 0;
            return;
          }
          if (dataStr.startsWith('[ERROR]')) {
            console.error('[transcription]', dataStr);
            state.value = 'IDLE';
            elapsedSeconds.value = 0;
            return;
          }
          try {
            const parsed = JSON.parse(dataStr);
            const text = typeof parsed === 'string' ? parsed : parsed.text ?? '';
            // Backend sends complete words with trailing whitespace (word-boundary buffering)
            api.insertTextAtCursor(text);
          } catch {
            // Server sends raw text chunks not wrapped in JSON — insert directly
            api.insertTextAtCursor(dataStr);
          }
        }
      }

      if (!response.ok) {
        console.error('[transcription] HTTP error:', response.status, response.statusText);
        state.value = 'IDLE';
        elapsedSeconds.value = 0;
        return;
      }
    } catch (err) {
      console.error('[transcription] error:', err);
    }
    state.value = 'IDLE';
    elapsedSeconds.value = 0;
  }

  async function startRecording() {
    pendingWavPath = null;
    state.value = 'RECORDING';
    elapsedSeconds.value = 0;
    timerInterval = setInterval(() => elapsedSeconds.value++, 1000);
    api.audioCommand({ action: 'start', mode: currentMode });
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
    if (timerInterval) { clearInterval(timerInterval); timerInterval = null; }
    if (state.value === 'RECORDING') {
      api.audioCommand({ action: 'stop' });
    }
    state.value = 'IDLE';
    elapsedSeconds.value = 0;
    rmsValue.value = 0;
    pendingWavPath = null;
  }

  function setMode(mode: 'mic' | 'system') {
    currentMode = mode;
  }

  cleanupRms = api.onRmsUpdate((value: number) => {
    rmsValue.value = value;
  });

  cleanupStatus = api.onAudioStatus((status) => {
    if (!status.recording && status.wav_path) {
      pendingWavPath = status.wav_path;
    }
  });

  onUnmounted(() => {
    if (timerInterval) clearInterval(timerInterval);
    cleanupRms?.();
    cleanupStatus?.();
  });

  return {
    transcriptionState: state,
    elapsedSeconds,
    rmsValue,
    currentMode,
    isShowingCancel: ref(state.value === 'RECORDING' || state.value === 'TRANSCRIBING'),
    handleRecordClick,
    handleCancel,
    setMode,
  };
}
