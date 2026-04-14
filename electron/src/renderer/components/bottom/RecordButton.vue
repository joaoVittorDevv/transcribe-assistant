<template>
  <div class="flex items-center gap-2">
    <!-- Mic/System toggle -->
    <button
      @click="toggleMode"
      class="glass-btn w-8 h-8 flex items-center justify-center rounded-full"
      :title="mode === 'mic' ? 'Microfone' : 'Audio do Sistema'"
    >
      <!-- Microphone icon -->
      <svg v-if="mode === 'mic'" xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z" />
      </svg>
      <!-- Speaker icon -->
      <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
        <path stroke-linecap="round" stroke-linejoin="round" d="M19.114 5.636a9 9 0 010 12.728M16.463 8.288a5.25 5.25 0 010 7.424M6.75 8.25l4.72-4.72a.75.75 0 011.28.53v13.94a.75.75 0 01-1.28.53l-4.72-4.72H4.51c-.88 0-1.704-.507-1.938-1.354A9.01 9.01 0 012.25 12c0-.83.112-1.633.322-2.396C2.806 6.057 3.63 5.55 4.51 5.55H6.75z" />
      </svg>
    </button>

    <!-- Record button -->
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
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import type { TranscriptionState } from '../../composables/useTranscriptionState';

const props = defineProps<{ state: TranscriptionState }>();
const emit = defineEmits<{
  click: [];
  'mode-change': [mode: 'mic' | 'system'];
}>();

const mode = ref<'mic' | 'system'>('mic');

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

function toggleMode() {
  mode.value = mode.value === 'mic' ? 'system' : 'mic';
  emit('mode-change', mode.value);
}

defineExpose({ mode });
</script>

<style scoped>
.record-btn {
  width: 72px;
  height: 72px;
  flex-shrink: 0;
}
</style>
