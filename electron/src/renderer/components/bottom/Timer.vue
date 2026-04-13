<template>
  <div class="glass-surface px-4 py-2 font-plus-jakarta text-sm font-semibold text-text-primary tabular-nums min-w-[64px] text-center">
    {{ formatted }}
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{ seconds: number }>();

const formatted = computed(() => {
  const m = Math.floor(props.seconds / 60).toString().padStart(2, '0');
  const s = (props.seconds % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
});
</script>
