import { ref, computed } from 'vue';
import { useTabs } from './useTabs';

export type TranscriptionState = 'IDLE' | 'RECORDING' | 'TRANSCRIBING';

const state = ref<TranscriptionState>('IDLE');
const elapsedSeconds = ref(0);
let timerInterval: ReturnType<typeof setInterval> | null = null;

const MOCK_TEXT =
  'Esta é uma transcrição de exemplo gerada automaticamente pelo sistema. ' +
  'O conteúdo real será inserido após a integração com os modelos de transcrição. ' +
  'Obrigado por usar o Transcribe Assistant.';

export function useTranscriptionState() {
  const { activeTabId, updateContent } = useTabs();

  const isShowingCancel = computed(
    () => state.value === 'RECORDING' || state.value === 'TRANSCRIBING'
  );

  function startTimer(): void {
    elapsedSeconds.value = 0;
    timerInterval = setInterval(() => {
      elapsedSeconds.value++;
    }, 1000);
  }

  function stopTimer(): void {
    if (timerInterval) {
      clearInterval(timerInterval);
      timerInterval = null;
    }
  }

  function handleRecordClick(): void {
    if (state.value === 'IDLE') {
      state.value = 'RECORDING';
      startTimer();
    } else if (state.value === 'RECORDING') {
      state.value = 'TRANSCRIBING';
      stopTimer();
      // Simulate transcription delay then insert mock text
      setTimeout(() => {
        if (state.value === 'TRANSCRIBING') {
          const existing = '';
          updateContent(activeTabId.value, existing + MOCK_TEXT);
          state.value = 'IDLE';
          elapsedSeconds.value = 0;
        }
      }, 1500);
    } else if (state.value === 'TRANSCRIBING') {
      // Manual advance: finish and insert
      updateContent(activeTabId.value, MOCK_TEXT);
      state.value = 'IDLE';
      elapsedSeconds.value = 0;
    }
  }

  function handleCancel(): void {
    stopTimer();
    state.value = 'IDLE';
    elapsedSeconds.value = 0;
  }

  return {
    transcriptionState: state,
    elapsedSeconds,
    isShowingCancel,
    handleRecordClick,
    handleCancel,
  };
}
