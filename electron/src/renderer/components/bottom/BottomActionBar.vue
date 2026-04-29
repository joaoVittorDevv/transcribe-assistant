<template>
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
          <path stroke-linecap="round" stroke-linejoin="round" d="M15.666 3.888A2.25 2.25 0 0013.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 01-.75.75H9a.75.75 0 01-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 01-2.25 2.25H6.75A2.25 2.25 0 014.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 011.927-.184" />
        </svg>
        {{ t('buttons.copy') }}
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
import Timer from './Timer.vue';
import AudioVisualizer from './AudioVisualizer.vue';
import RecordButton from './RecordButton.vue';
import { useTranscriptionState } from '../../composables/useTranscriptionState';
import { useTabs } from '../../composables/useTabs';
import { useEditor } from '../../composables/useEditor';
import { useClipboard } from '../../composables/useClipboard';
import { t } from '../../i18n';

const { transcriptionState, elapsedSeconds, isShowingCancel, handleRecordClick, handleCancel, setMode } = useTranscriptionState();
const { resetActiveTab } = useTabs();
const { clearEditor, getMarkdown } = useEditor();
const { copyToClipboard } = useClipboard();

function handleCopy() {
  const markdown = getMarkdown();
  if (markdown) copyToClipboard(markdown);
}

function handleReset() {
  clearEditor();
  resetActiveTab();
}

function handleModeChange(mode: 'mic' | 'system') {
  setMode(mode);
}
</script>
