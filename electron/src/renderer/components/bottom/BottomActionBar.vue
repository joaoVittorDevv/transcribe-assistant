<template>
  <!-- Transcription progress indicator -->
  <Transition name="progress-slide">
    <TranscriptionProgress v-if="transcriptionState === 'TRANSCRIBING'" />
  </Transition>

  <!-- Undo Toast -->
  <Transition name="toast-slide">
    <div
      v-if="showUndoToast"
      class="flex items-center justify-between gap-3 px-4 py-2.5 mx-4 mb-2 glass-surface rounded-xl"
    >
      <span class="text-xs text-text-primary">{{ t('toast.content_cleared') }}</span>
      <button
        @click="handleUndo"
        class="text-xs font-semibold text-accent-blue hover:text-blue-400 transition-colors duration-100 px-2 py-1 rounded-lg hover:bg-white/5"
      >{{ t('toast.undo') }}</button>
    </div>
  </Transition>

  <div class="flex items-center gap-3 px-4 py-3 border-t border-white/10">
    <!-- Left: Timer -->
    <Timer :seconds="elapsedSeconds" />

    <!-- Center-left: Visualizer -->
    <AudioVisualizer :is-active="transcriptionState === 'RECORDING'" />

    <!-- Center: Record button (always centered) -->
    <div class="flex-1 flex items-center justify-center">
      <RecordButton
        :state="transcriptionState"
        :cancel-visible="isShowingCancel"
        @click="handleRecordClick"
        @cancel="handleCancel"
        @mode-change="handleModeChange"
      />
    </div>

    <!-- Right: Copy + Reset -->
    <div class="flex items-center gap-2">
      <button @click="handleCopy" class="glass-btn flex items-center gap-1.5 text-xs py-1.5 px-3">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
          <path v-if="copyFeedback === 'idle'" stroke-linecap="round" stroke-linejoin="round" d="M15.666 3.888A2.25 2.25 0 0013.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 01-.75.75H9a.75.75 0 01-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 01-2.25 2.25H6.75A2.25 2.25 0 014.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 011.927-.184" />
          <path v-else-if="copyFeedback === 'success'" stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5" />
          <path v-else stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
        <span v-if="copyFeedback === 'idle'">{{ t('buttons.copy') }}</span>
        <span v-else-if="copyFeedback === 'success'" class="text-green-400">{{ t('toast.copied') }}</span>
        <span v-else class="text-red-400">{{ t('toast.copy_error') }}</span>
      </button>
      <button @click="handleReset" class="glass-btn flex items-center gap-1.5 text-xs py-1.5 px-3">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
        </svg>
        {{ t('buttons.reset') }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onUnmounted } from 'vue';
import Timer from './Timer.vue';
import AudioVisualizer from './AudioVisualizer.vue';
import RecordButton from './RecordButton.vue';
import TranscriptionProgress from './TranscriptionProgress.vue';
import { useTranscriptionState } from '../../composables/useTranscriptionState';
import { useTabs } from '../../composables/useTabs';
import { useEditor } from '../../composables/useEditor';
import { useClipboard } from '../../composables/useClipboard';
import { t } from '../../i18n';
import type { ElectronAPI } from '../../types/global';

const api = window.electronAPI as ElectronAPI;
const { transcriptionState, elapsedSeconds, isShowingCancel, handleRecordClick, handleCancel, setMode } = useTranscriptionState();
const { resetActiveTab, getActiveTab } = useTabs();
const { clearEditor, getMarkdown, undo } = useEditor();
const { copyToClipboard } = useClipboard();

const showUndoToast = ref(false);
const copyFeedback = ref<'idle' | 'success' | 'error'>('idle');
let undoToastTimer: ReturnType<typeof setTimeout> | null = null;
let copyFeedbackTimer: ReturnType<typeof setTimeout> | null = null;

async function handleCopy() {
  let markdown = getMarkdown();
  if (!markdown) {
    markdown = getActiveTab()?.content || '';
  }
  if (!markdown) return;

  const ok = await copyToClipboard(markdown);
  copyFeedback.value = ok ? 'success' : 'error';
  if (copyFeedbackTimer) clearTimeout(copyFeedbackTimer);
  copyFeedbackTimer = setTimeout(() => {
    copyFeedback.value = 'idle';
    copyFeedbackTimer = null;
  }, 2000);
}

function handleReset() {
  // If transcription is active, abort it first to prevent ghost text insertion
  if (transcriptionState.value === 'TRANSCRIBING') {
    handleCancel();
  }

  // Reset editor insertion tracking so stale index doesn't cause misplaced text
  api.resetInsertionPoint();

  clearEditor();
  resetActiveTab();

  // Show undo toast
  showUndoToast.value = true;
  if (undoToastTimer) clearTimeout(undoToastTimer);
  undoToastTimer = setTimeout(() => {
    showUndoToast.value = false;
    undoToastTimer = null;
  }, 6000);
}

function handleUndo() {
  undo();
  showUndoToast.value = false;
  if (undoToastTimer) {
    clearTimeout(undoToastTimer);
    undoToastTimer = null;
  }
}

function handleModeChange(mode: 'mic' | 'system' | 'dual') {
  setMode(mode);
}

onUnmounted(() => {
  if (undoToastTimer) clearTimeout(undoToastTimer);
  if (copyFeedbackTimer) clearTimeout(copyFeedbackTimer);
});
</script>

<style scoped>
.progress-slide-enter-active {
  transition: all 0.3s ease-out;
}
.progress-slide-leave-active {
  transition: all 0.2s ease-in;
}
.progress-slide-enter-from {
  opacity: 0;
  transform: translateY(-10px);
  max-height: 0;
}
.progress-slide-enter-to {
  opacity: 1;
  transform: translateY(0);
  max-height: 120px;
}
.progress-slide-leave-from {
  opacity: 1;
  transform: translateY(0);
  max-height: 120px;
}
.progress-slide-leave-to {
  opacity: 0;
  transform: translateY(-10px);
  max-height: 0;
}

/* Toast animation */
.toast-slide-enter-active {
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
.toast-slide-leave-active {
  transition: all 0.2s ease-in;
}
.toast-slide-enter-from {
  opacity: 0;
  transform: translateY(8px);
  max-height: 0;
  margin-bottom: 0;
}
.toast-slide-enter-to {
  opacity: 1;
  transform: translateY(0);
  max-height: 60px;
}
.toast-slide-leave-from {
  opacity: 1;
  transform: translateY(0);
  max-height: 60px;
}
.toast-slide-leave-to {
  opacity: 0;
  transform: translateY(8px);
  max-height: 0;
  margin-bottom: 0;
}
</style>
