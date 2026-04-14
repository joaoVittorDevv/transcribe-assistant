<template>
  <div class="flex items-end gap-0.5 h-8 px-2">
    <div
      v-for="(bar, i) in bars"
      :key="i"
      class="w-1.5 rounded-full bg-accent-blue transition-all duration-150"
      :style="{ height: bar + 'px' }"
    ></div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onUnmounted } from 'vue';
import { useTranscriptionState } from '../../composables/useTranscriptionState';

const props = defineProps<{ isActive: boolean }>();
const NUM_BARS = 10;
const bars = ref<number[]>(new Array(NUM_BARS).fill(4));
const { rmsValue } = useTranscriptionState();

watch(() => props.isActive, (active) => {
  if (!active) {
    bars.value = bars.value.map(() => 4);
  }
}, { immediate: true });

watch(rmsValue, (rms) => {
  if (!props.isActive) return;
  bars.value = bars.value.map((_, i) => {
    const center = NUM_BARS / 2;
    const dist = Math.abs(i - center) / center;
    const scale = 1 - dist * 0.5;
    return Math.round(4 + rms * 24 * scale);
  });
});

onUnmounted(() => {});
</script>
