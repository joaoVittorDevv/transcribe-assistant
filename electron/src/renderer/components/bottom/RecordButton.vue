<template>
  <button
    @click="emit('click')"
    class="record-btn glass-surface rounded-full flex items-center justify-center transition-all duration-150"
    :class="stateClass"
    :title="label"
  >
    <!-- IDLE: microphone icon -->
    <svg v-if="state === 'IDLE'" xmlns="http://www.w3.org/2000/svg" class="h-8 w-8 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
      <path stroke-linecap="round" stroke-linejoin="round" d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z" />
    </svg>
    <!-- RECORDING: stop square -->
    <svg v-else-if="state === 'RECORDING'" xmlns="http://www.w3.org/2000/svg" class="h-8 w-8 text-red-500" viewBox="0 0 24 24" fill="currentColor">
      <rect x="6" y="6" width="12" height="12" rx="2" />
    </svg>
    <!-- TRANSCRIBING: spinner -->
    <svg v-else class="h-8 w-8 text-accent-blue animate-spin" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
    </svg>
  </button>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { TranscriptionState } from '../../composables/useTranscriptionState';

const props = defineProps<{ state: TranscriptionState }>();
const emit = defineEmits<{ click: [] }>();

const label = computed(() => {
  if (props.state === 'IDLE') return 'Gravar';
  if (props.state === 'RECORDING') return 'Parar';
  return 'Transcrevendo...';
});

const stateClass = computed(() => {
  if (props.state === 'RECORDING') return 'ring-2 ring-red-400 ring-offset-2 ring-offset-transparent';
  if (props.state === 'TRANSCRIBING') return 'ring-2 ring-accent-blue ring-offset-2 ring-offset-transparent';
  return '';
});
</script>

<style scoped>
.record-btn {
  width: 72px;
  height: 72px;
  flex-shrink: 0;
}
</style>
