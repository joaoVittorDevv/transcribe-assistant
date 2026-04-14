<template>
  <div class="flex items-center gap-3 px-4 py-3 border-t border-white/10">
    <!-- Left: Timer -->
    <Timer :seconds="elapsedSeconds" />

    <!-- Center-left: Visualizer -->
    <AudioVisualizer :is-active="transcriptionState === 'RECORDING'" />

    <!-- Center: Record button -->
    <div class="flex-1 flex items-center justify-center gap-3">
      <RecordButton :state="transcriptionState" @click="handleRecordClick" />
      <CancelButton :visible="isShowingCancel" @click="handleCancel" />
    </div>

    <!-- Right: Reset -->
    <div class="flex items-center gap-2">
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
import CancelButton from './CancelButton.vue';
import { useTranscriptionState } from '../../composables/useTranscriptionState';
import { useTabs } from '../../composables/useTabs';
import { useEditor } from '../../composables/useEditor';
import { t } from '../../i18n';

const { transcriptionState, elapsedSeconds, isShowingCancel, handleRecordClick, handleCancel } = useTranscriptionState();
const { resetActiveTab } = useTabs();
const { clearEditor } = useEditor();

function handleReset() {
  clearEditor();
  resetActiveTab();
}
</script>
