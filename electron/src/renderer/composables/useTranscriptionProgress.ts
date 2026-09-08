import { ref, computed } from 'vue';

export type ProgressPhase =
  | 'idle'
  | 'received'
  | 'saved'
  | 'processing'
  | 'uploading'
  | 'transcribing'
  | 'streaming'
  | 'reviewing'
  | 'done'
  | 'error';

export interface ProgressStep {
  id: ProgressPhase;
  labelKey: string;
  icon: string;
}

export const PROGRESS_STEPS: ProgressStep[] = [
  { id: 'received', labelKey: 'progress.step.received', icon: 'inbox' },
  { id: 'saved', labelKey: 'progress.step.saved', icon: 'save' },
  { id: 'processing', labelKey: 'progress.step.processing', icon: 'cpu' },
  { id: 'uploading', labelKey: 'progress.step.uploading', icon: 'upload' },
  { id: 'transcribing', labelKey: 'progress.step.transcribing', icon: 'brain' },
  { id: 'streaming', labelKey: 'progress.step.streaming', icon: 'stream' },
  { id: 'reviewing', labelKey: 'progress.step.reviewing', icon: 'review' },
  { id: 'done', labelKey: 'progress.step.done', icon: 'check' },
];

// Module-level shared state (singleton pattern matching useTranscriptionState)
const currentPhase = ref<ProgressPhase>('idle');
const statusMessage = ref<string>('');
const errorMessage = ref<string>('');
const erroredStepId = ref<ProgressPhase | null>(null);

export function useTranscriptionProgress() {
  function setPhase(phase: ProgressPhase, message?: string) {
    if (phase === 'error') {
      erroredStepId.value = currentPhase.value;
      if (message) errorMessage.value = message;
    }
    currentPhase.value = phase;
    if (message && phase !== 'error') {
      statusMessage.value = message;
    }
  }

  function reset() {
    currentPhase.value = 'idle';
    statusMessage.value = '';
    errorMessage.value = '';
    erroredStepId.value = null;
  }

  function isStepErrored(stepId: ProgressPhase): boolean {
    return erroredStepId.value === stepId;
  }

  function dismissError() {
    reset();
  }

  const activeIndex = computed(() => {
    if (currentPhase.value === 'idle') return -1;
    return PROGRESS_STEPS.findIndex((s) => s.id === currentPhase.value);
  });

  const isStepCompleted = (stepId: ProgressPhase) => {
    const stepIdx = PROGRESS_STEPS.findIndex((s) => s.id === stepId);
    return activeIndex.value > stepIdx;
  };

  const isStepActive = (stepId: ProgressPhase) => {
    return currentPhase.value === stepId;
  };

  const isStepPending = (stepId: ProgressPhase) => {
    const stepIdx = PROGRESS_STEPS.findIndex((s) => s.id === stepId);
    return activeIndex.value < stepIdx;
  };

  const progressPercent = computed(() => {
    if (activeIndex.value < 0) return 0;
    return Math.round(((activeIndex.value + 1) / PROGRESS_STEPS.length) * 100);
  });

  return {
    currentPhase,
    statusMessage,
    errorMessage,
    erroredStepId,
    activeIndex,
    progressPercent,
    setPhase,
    reset,
    isStepCompleted,
    isStepActive,
    isStepPending,
    isStepErrored,
    dismissError,
  };
}
