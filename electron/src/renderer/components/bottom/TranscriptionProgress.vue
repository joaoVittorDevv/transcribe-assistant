<template>
  <div class="transcription-progress px-4 py-2">
    <!-- Step indicator -->
    <div class="flex items-center justify-between relative">
      <!-- Connecting line background -->
      <div class="step-line absolute top-3 left-3 right-3 h-0.5 bg-white/10 rounded-full" />

      <!-- Connecting line progress -->
      <div
        class="step-line-fill absolute top-3 left-3 h-0.5 rounded-full bg-accent-blue transition-all duration-500 ease-out"
        :style="{ width: lineWidth }"
      />

      <div
        v-for="step in steps"
        :key="step.id"
        class="step-node relative z-10 flex flex-col items-center"
        :class="stepNodeClass(step.id)"
      >
        <!-- Step circle -->
        <div
          class="step-circle w-6 h-6 rounded-full flex items-center justify-center transition-all duration-300"
          :class="stepCircleClass(step.id)"
        >
          <!-- Completed: checkmark -->
          <svg
            v-if="isStepCompleted(step.id)"
            xmlns="http://www.w3.org/2000/svg"
            class="h-3.5 w-3.5 text-white"
            viewBox="0 0 20 20"
            fill="currentColor"
          >
            <path
              fill-rule="evenodd"
              d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
              clip-rule="evenodd"
            />
          </svg>
          <!-- Active/Pending: step icon -->
          <component
            v-else
            :is="getStepIcon(step.icon)"
            class="h-3 w-3"
          />
        </div>

        <!-- Step label -->
        <span
          class="step-label text-[9px] mt-1 whitespace-nowrap transition-colors duration-300"
          :class="isStepActive(step.id) ? 'text-accent-blue' : isStepCompleted(step.id) ? 'text-accent-green/70' : 'text-white/30'"
        >
          {{ t(step.labelKey as any) }}
        </span>
      </div>
    </div>

    <!-- Status message -->
    <div class="mt-2 text-center">
      <p
        class="text-xs status-message"
        :class="{
          'text-white/60': currentPhase !== 'error',
          'text-red-400': currentPhase === 'error',
          'status-active': currentPhase !== 'idle' && currentPhase !== 'done' && currentPhase !== 'error'
        }"
      >
        {{ currentPhase === 'error' ? (errorMsg || t('progress.default_message')) : (statusMessage || t('progress.default_message')) }}
      </p>
    </div>

    <!-- Progress bar -->
    <div class="mt-2 h-1 w-full rounded-full bg-white/5 overflow-hidden">
      <div
        class="progress-bar-fill h-full rounded-full transition-all duration-500 ease-out"
        :class="currentPhase === 'done' ? 'bg-accent-green' : currentPhase === 'error' ? 'bg-red-500' : 'bg-accent-blue'"
        :style="{ width: progressPercent + '%' }"
      />
    </div>

    <!-- Dismiss button on error -->
    <div v-if="currentPhase === 'error'" class="mt-2 flex justify-center">
      <button
        @click="closeError"
        class="error-dismiss-btn text-xs px-3 py-1 rounded bg-red-500/20 border border-red-500/50 text-red-300 hover:bg-red-500/30 transition-colors"
      >
        ✕ Fechar
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, h, type FunctionalComponent } from 'vue';
import { useTranscriptionProgress, PROGRESS_STEPS, type ProgressPhase } from '../../composables/useTranscriptionProgress';
import { t } from '../../i18n';

// Destructure error-related exports (module-level singletons so destructure separately)
const { errorMessage: errorMsg, isStepErrored: stepErrored, dismissError: closeError } = useTranscriptionProgress();

const {
  currentPhase,
  statusMessage,
  progressPercent,
  isStepCompleted,
  isStepActive,
} = useTranscriptionProgress();

const steps = PROGRESS_STEPS;

// SVG icon components for each step
const InboxIcon: FunctionalComponent = () =>
  h('svg', { xmlns: 'http://www.w3.org/2000/svg', fill: 'none', viewBox: '0 0 24 24', stroke: 'currentColor', 'stroke-width': '2' }, [
    h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', d: 'M2.25 13.5h3.86a2.25 2.25 0 012.012 1.244l.256.512a2.25 2.25 0 002.013 1.244h3.218a2.25 2.25 0 002.013-1.244l.256-.512a2.25 2.25 0 012.013-1.244h3.859m-19.5.338V18a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18v-4.162c0-.224-.034-.447-.1-.661L19.24 5.256a2.25 2.25 0 00-2.12-1.588H6.88a2.25 2.25 0 00-2.12 1.588L2.35 13.177a2.25 2.25 0 00-.1.661z' }),
  ]);

const SaveIcon: FunctionalComponent = () =>
  h('svg', { xmlns: 'http://www.w3.org/2000/svg', fill: 'none', viewBox: '0 0 24 24', stroke: 'currentColor', 'stroke-width': '2' }, [
    h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', d: 'M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0111.186 0z' }),
  ]);

const CpuIcon: FunctionalComponent = () =>
  h('svg', { xmlns: 'http://www.w3.org/2000/svg', fill: 'none', viewBox: '0 0 24 24', stroke: 'currentColor', 'stroke-width': '2' }, [
    h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', d: 'M8.25 3v1.5M4.5 8.25H3m18 0h-1.5M4.5 12H3m18 0h-1.5m-15 3.75H3m18 0h-1.5M8.25 19.5V21M12 3v1.5m0 15V21m3.75-18v1.5m0 15V21m-9-1.5h10.5a2.25 2.25 0 002.25-2.25V6.75a2.25 2.25 0 00-2.25-2.25H6.75A2.25 2.25 0 004.5 6.75v10.5a2.25 2.25 0 002.25 2.25zm.75-12h9v9h-9v-9z' }),
  ]);

const UploadIcon: FunctionalComponent = () =>
  h('svg', { xmlns: 'http://www.w3.org/2000/svg', fill: 'none', viewBox: '0 0 24 24', stroke: 'currentColor', 'stroke-width': '2' }, [
    h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', d: 'M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5' }),
  ]);

const BrainIcon: FunctionalComponent = () =>
  h('svg', { xmlns: 'http://www.w3.org/2000/svg', fill: 'none', viewBox: '0 0 24 24', stroke: 'currentColor', 'stroke-width': '2' }, [
    h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', d: 'M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23.693L5 14.5m14.8.8l1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0112 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5' }),
  ]);

const StreamIcon: FunctionalComponent = () =>
  h('svg', { xmlns: 'http://www.w3.org/2000/svg', fill: 'none', viewBox: '0 0 24 24', stroke: 'currentColor', 'stroke-width': '2' }, [
    h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', d: 'M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z' }),
  ]);

const CheckCircleIcon: FunctionalComponent = () =>
  h('svg', { xmlns: 'http://www.w3.org/2000/svg', fill: 'none', viewBox: '0 0 24 24', stroke: 'currentColor', 'stroke-width': '2' }, [
    h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', d: 'M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z' }),
  ]);

const ReviewIcon: FunctionalComponent = () =>
  h('svg', { xmlns: 'http://www.w3.org/2000/svg', fill: 'none', viewBox: '0 0 24 24', stroke: 'currentColor', 'stroke-width': '2' }, [
    h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', d: 'M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 002.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 00-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 00.75-.75 2.25 2.25 0 00-.1-.664m-5.8 0A2.251 2.251 0 0113.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25zM6.75 12h.008v.008H6.75V12zm0 3h.008v.008H6.75V15zm0 3h.008v.008H6.75V18z' }),
  ]);

const iconMap: Record<string, FunctionalComponent> = {
  inbox: InboxIcon,
  save: SaveIcon,
  cpu: CpuIcon,
  upload: UploadIcon,
  brain: BrainIcon,
  stream: StreamIcon,
  review: ReviewIcon,
  check: CheckCircleIcon,
};

function getStepIcon(iconName: string): FunctionalComponent {
  return iconMap[iconName] ?? CheckCircleIcon;
}

// Computed width of the connecting progress line
const lineWidth = computed(() => {
  if (steps.length <= 1) return '0%';
  const pct = (Math.max(0, steps.findIndex((s) => s.id === currentPhase.value)) / (steps.length - 1)) * 100;
  return `calc(${pct}% - 0px)`;
});

function stepNodeClass(_stepId: string) {
  return {};
}

function stepCircleClass(stepId: string) {
  const phase = stepId as ProgressPhase;
  if (stepErrored(phase)) {
    return 'bg-red-500 shadow-[0_0_12px_rgba(239,68,68,0.5)] error-glow';
  }
  if (isStepCompleted(phase)) {
    return 'bg-accent-green shadow-[0_0_8px_rgba(34,197,94,0.4)]';
  }
  if (isStepActive(phase)) {
    return 'bg-accent-blue shadow-[0_0_12px_rgba(59,130,246,0.5)] step-active-glow';
  }
  return 'bg-white/10 border border-white/20';
}
</script>

<style scoped>
.transcription-progress {
  animation: fadeSlideIn 0.3s ease-out;
}

@keyframes fadeSlideIn {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.step-active-glow {
  animation: pulseGlow 2s ease-in-out infinite;
}

@keyframes pulseGlow {
  0%, 100% {
    box-shadow: 0 0 8px rgba(59, 130, 246, 0.4);
  }
  50% {
    box-shadow: 0 0 16px rgba(59, 130, 246, 0.7);
  }
}

.progress-bar-fill {
  position: relative;
  overflow: hidden;
}

.progress-bar-fill::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(255, 255, 255, 0.3) 50%,
    transparent 100%
  );
  animation: shimmer 1.5s ease-in-out infinite;
}

@keyframes shimmer {
  0% {
    transform: translateX(-100%);
  }
  100% {
    transform: translateX(100%);
  }
}

.status-active {
  animation: statusPulse 3s ease-in-out infinite;
}

.error-glow {
  animation: errorPulse 1.5s ease-in-out infinite;
}

@keyframes errorPulse {
  0%, 100% {
    box-shadow: 0 0 8px rgba(239, 68, 68, 0.4);
  }
  50% {
    box-shadow: 0 0 16px rgba(239, 68, 68, 0.7);
  }
}

@keyframes statusPulse {
  0%, 100% {
    opacity: 0.6;
  }
  50% {
    opacity: 1;
  }
}

.step-line-fill {
  max-width: calc(100% - 1.5rem);
}
</style>
