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

const props = defineProps<{ isActive: boolean }>();

const NUM_BARS = 10;
const bars = ref<number[]>(new Array(NUM_BARS).fill(4));

let animFrame: ReturnType<typeof setInterval> | null = null;

watch(() => props.isActive, (active) => {
  if (active) {
    animFrame = setInterval(() => {
      bars.value = bars.value.map(() =>
        Math.floor(Math.random() * 24) + 4
      );
    }, 120);
  } else {
    if (animFrame) {
      clearInterval(animFrame);
      animFrame = null;
    }
    bars.value = bars.value.map(() => 4);
  }
}, { immediate: true });

onUnmounted(() => {
  if (animFrame) clearInterval(animFrame);
});
</script>
