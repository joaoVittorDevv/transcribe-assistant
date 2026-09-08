<template>
  <div
    class="tab-item group flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-inter font-medium cursor-pointer transition-all duration-150 select-none border"
    :class="isActive ? 'bg-[#1A1D24] text-[#DDE2F6] border-[#3F444E] shadow-sm' : 'text-[#909095] border-transparent hover:text-[#DDE2F6] hover:bg-[#1A1D24]/60'"
    @click="emit('activate')"
  >
    <span class="w-1.5 h-1.5 rounded-full" :class="isActive ? 'bg-[#F59E0B]' : 'bg-transparent'"></span>
    <span class="truncate max-w-[120px]">{{ tab.title }}</span>
    <button
      v-if="canClose"
      @click.stop="emit('close')"
      class="opacity-0 group-hover:opacity-100 transition-opacity rounded p-0.5 hover:bg-[#2D3342] text-[#909095] hover:text-[#DDE2F6]"
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
