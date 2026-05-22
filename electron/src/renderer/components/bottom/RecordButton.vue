<template>
  <div class="flex items-center w-full">
    <!-- Left section: mode selector + indicator, pushed right toward record button -->
    <div class="flex-1 flex justify-end items-center">
      <div class="relative flex items-center gap-1 mr-2" ref="modeContainerRef">
        <button
          @click="toggleDropup"
          class="glass-btn w-8 h-8 flex items-center justify-center rounded-full"
          :title="modeTitle"
          ref="modeBtnRef"
        >
          <!-- Microphone icon -->
          <svg v-if="mode === 'mic'" xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z" />
          </svg>
          <!-- Speaker icon -->
          <svg v-else-if="mode === 'system'" xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M19.114 5.636a9 9 0 010 12.728M16.463 8.288a5.25 5.25 0 010 7.424M6.75 8.25l4.72-4.72a.75.75 0 011.28.53v13.94a.75.75 0 01-1.28.53l-4.72-4.72H4.51c-.88 0-1.704-.507-1.938-1.354A9.01 9.01 0 012.25 12c0-.83.112-1.633.322-2.396C2.806 6.057 3.63 5.55 4.51 5.55H6.75z" />
          </svg>
          <!-- Union icon: mic + speaker combined -->
          <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z" />
            <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 5.625a2.25 2.25 0 010 4.5M18 8.25a5.25 5.25 0 010 7.5" transform="translate(0.5, -1)" />
          </svg>
        </button>
        <!-- Mode label indicator -->
        <span
          v-if="mode === 'system'"
          class="text-[10px] text-accent-blue font-medium tracking-wide"
          :title="t('transcription.system_gemini_hint')"
        >Gemini</span>
        <span
          v-if="mode === 'dual'"
          class="text-[10px] text-accent-blue font-medium tracking-wide"
          :title="t('audio.dual_description')"
        >Dual</span>

        <!-- Dropup Menu -->
        <Transition name="dropup-fade">
          <div
            v-if="dropupOpen"
            class="dropup-menu glass-surface absolute left-0 min-w-[200px] py-1.5 z-50"
            ref="dropupRef"
          >
            <!-- Microphone -->
            <button
              @click="selectMode('mic')"
              class="dropup-item w-full flex items-center gap-2.5 px-3 py-2 text-xs text-left transition-colors duration-100"
              :class="mode === 'mic' ? 'text-accent-blue' : 'text-text-primary hover:bg-white/5'"
            >
              <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z" />
              </svg>
              <span class="flex-1">{{ t('audio.microphone') }}</span>
              <svg v-if="mode === 'mic'" xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5 text-accent-blue" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
              </svg>
            </button>

            <!-- System Audio -->
            <button
              @click="selectMode('system')"
              class="dropup-item w-full flex items-center gap-2.5 px-3 py-2 text-xs text-left transition-colors duration-100"
              :class="mode === 'system' ? 'text-accent-blue' : 'text-text-primary hover:bg-white/5'"
            >
              <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M19.114 5.636a9 9 0 010 12.728M16.463 8.288a5.25 5.25 0 010 7.424M6.75 8.25l4.72-4.72a.75.75 0 011.28.53v13.94a.75.75 0 01-1.28.53l-4.72-4.72H4.51c-.88 0-1.704-.507-1.938-1.354A9.01 9.01 0 012.25 12c0-.83.112-1.633.322-2.396C2.806 6.057 3.63 5.55 4.51 5.55H6.75z" />
              </svg>
              <span class="flex-1">{{ t('audio.system') }} (Gemini)</span>
              <svg v-if="mode === 'system'" xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5 text-accent-blue" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
              </svg>
            </button>

            <!-- Divider -->
            <div class="border-t border-white/5 my-1"></div>

            <!-- Dual -->
            <button
              @click="selectMode('dual')"
              class="dropup-item w-full flex items-center gap-2.5 px-3 py-2 text-xs text-left transition-colors duration-100"
              :class="mode === 'dual' ? 'text-accent-blue' : 'text-text-primary hover:bg-white/5'"
            >
              <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z" />
                <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 5.625a2.25 2.25 0 010 4.5M18 8.25a5.25 5.25 0 010 7.5" transform="translate(0.5, -1)" />
              </svg>
              <span class="flex-1">{{ t('audio.dual_description') }}</span>
              <svg v-if="mode === 'dual'" xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5 text-accent-blue" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
              </svg>
            </button>
          </div>
        </Transition>
      </div>
    </div>

    <!-- Record button — always centered -->
    <button
      @click="emit('click')"
      class="record-btn glass-surface rounded-full flex items-center justify-center transition-all duration-150 flex-shrink-0"
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

    <!-- Right section: cancel button, pushed left toward record button. Equal flex-1 to left section keeps record centered. -->
    <div class="flex-1 flex justify-start items-center">
      <button
        v-show="cancelVisible"
        @click="emit('cancel')"
        class="glass-btn w-8 h-8 flex items-center justify-center rounded-full ml-2"
        title="Cancelar"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-accent-red" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
        </svg>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onUnmounted } from 'vue';
import { t } from '../../i18n';
import type { TranscriptionState } from '../../composables/useTranscriptionState';

const props = defineProps<{
  state: TranscriptionState;
  cancelVisible: boolean;
}>();
const emit = defineEmits<{
  click: [];
  cancel: [];
  'mode-change': [mode: 'mic' | 'system' | 'dual'];
}>();

const mode = ref<'mic' | 'system' | 'dual'>('mic');
const dropupOpen = ref(false);
const modeContainerRef = ref<HTMLElement | null>(null);
const modeBtnRef = ref<HTMLElement | null>(null);
const dropupRef = ref<HTMLElement | null>(null);

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

const modeTitle = computed(() => {
  if (mode.value === 'mic') return t('audio.microphone');
  if (mode.value === 'system') return t('audio.system') + ' (Gemini)';
  return t('audio.dual_description');
});

function toggleDropup() {
  dropupOpen.value = !dropupOpen.value;
  if (dropupOpen.value) {
    // Add click-outside listener on next tick
    setTimeout(() => document.addEventListener('click', handleClickOutside), 0);
  } else {
    document.removeEventListener('click', handleClickOutside);
  }
}

function handleClickOutside(e: MouseEvent) {
  const target = e.target as Node;
  if (
    modeContainerRef.value &&
    !modeContainerRef.value.contains(target)
  ) {
    dropupOpen.value = false;
    document.removeEventListener('click', handleClickOutside);
  }
}

function selectMode(newMode: 'mic' | 'system' | 'dual') {
  mode.value = newMode;
  emit('mode-change', newMode);
  dropupOpen.value = false;
  document.removeEventListener('click', handleClickOutside);
}

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside);
});

defineExpose({ mode });
</script>

<style scoped>
.record-btn {
  width: 72px;
  height: 72px;
  flex-shrink: 0;
}

.dropup-menu {
  bottom: calc(100% + 8px);
  border-radius: 12px;
  box-shadow: 0 -4px 24px rgba(0, 0, 0, 0.3), 0 0 0 1px rgba(255, 255, 255, 0.06);
}

.dropup-item {
  border-radius: 8px;
  margin: 0 4px;
  width: calc(100% - 8px);
}

/* Dropup animation */
.dropup-fade-enter-active {
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}
.dropup-fade-leave-active {
  transition: all 0.15s ease-in;
}
.dropup-fade-enter-from {
  opacity: 0;
  transform: translateY(8px) scale(0.95);
}
.dropup-fade-leave-to {
  opacity: 0;
  transform: translateY(4px) scale(0.98);
}
</style>

