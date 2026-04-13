<template>
  <div
    class="tab-item group flex items-center gap-1.5 px-3 py-2 rounded-xl text-sm font-plus-jakarta font-medium cursor-pointer transition-all duration-150 select-none"
    :class="isActive ? 'glass-surface text-accent-blue' : 'text-text-muted hover:text-text-primary'"
    @click="emit('activate')"
  >
    <span class="truncate max-w-[80px]">{{ tab.title }}</span>
    <button
      v-if="canClose"
      @click.stop="emit('close')"
      class="opacity-0 group-hover:opacity-100 transition-opacity rounded-md p-0.5 hover:bg-black/10"
    >
      <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3" viewBox="0 0 20 20" fill="currentColor">
        <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
      </svg>
    </button>
  </div>
</template>

<script setup lang="ts">
import type { Tab } from '../../composables/useTabs';

defineProps<{
  tab: Tab;
  isActive: boolean;
  canClose: boolean;
}>();

const emit = defineEmits<{
  activate: [];
  close: [];
}>();
</script>
