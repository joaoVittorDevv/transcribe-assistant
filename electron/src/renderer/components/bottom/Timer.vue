<template>
  <div class="bg-[#13151A] border border-[#2D3342] rounded px-2.5 py-1 font-mono text-xs font-semibold text-[#DDE2F6] tabular-nums min-w-[56px] text-center shadow-inner">
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
