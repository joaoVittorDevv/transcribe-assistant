<template>
  <div
    v-if="visible"
    class="find-replace-bar glass-surface flex flex-col gap-2 p-3 rounded-xl animate-slide-in"
  >
    <!-- Search row -->
    <div class="flex items-center gap-2">
      <div class="flex-1 relative">
        <svg
          class="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-gray-400"
          fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"
        >
          <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
        </svg>
        <input
          ref="searchInputEl"
          v-model="searchText"
          type="text"
          :placeholder="t('find.search_placeholder')"
          class="w-full bg-white/5 border border-white/10 rounded-lg py-1.5 pl-8 pr-3 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-accent-blue/50"
          @input="onSearchInput"
          @keydown="onKeydown"
        />
      </div>

      <span class="text-xs text-gray-400 min-w-[60px] text-right tabular-nums">
        {{ matchCountText }}
      </span>

      <button
        class="p-1.5 rounded-md hover:bg-white/10 text-gray-400 hover:text-gray-200 transition-colors"
        :title="t('find.previous')"
        @click="$emit('prev')"
      >
        <svg class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M5 15l7-7 7 7" />
        </svg>
      </button>
      <button
        class="p-1.5 rounded-md hover:bg-white/10 text-gray-400 hover:text-gray-200 transition-colors"
        :title="t('find.next')"
        @click="$emit('next')"
      >
        <svg class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      <button
        class="p-1.5 rounded-md hover:bg-white/10 text-gray-400 hover:text-red-400 transition-colors"
        :title="t('find.close')"
        @click="$emit('close')"
      >
        <svg class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>

    <!-- Replace row -->
    <div class="flex items-center gap-2">
      <div class="flex-1 relative">
        <input
          v-model="replaceText"
          type="text"
          :placeholder="t('find.replace_placeholder')"
          class="w-full bg-white/5 border border-white/10 rounded-lg py-1.5 px-3 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-accent-blue/50"
          @keydown="onReplaceKeydown"
        />
      </div>
      <button
        class="px-2.5 py-1 text-xs font-medium rounded-md bg-white/10 text-gray-300 hover:bg-white/20 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
        :disabled="!canReplace"
        @click="$emit('replace')"
      >
        {{ t('find.replace') }}
      </button>
      <button
        class="px-2.5 py-1 text-xs font-medium rounded-md bg-accent-blue/20 text-accent-blue hover:bg-accent-blue/30 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
        :disabled="!canReplace"
        @click="$emit('replace-all')"
      >
        {{ t('find.replace_all') }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue';
import { t } from '../../i18n';

const props = defineProps<{
  visible: boolean;
  matchCount: number;
  activeMatchIndex: number;
}>();

const emit = defineEmits<{
  search: [text: string];
  next: [];
  prev: [];
  replace: [];
  'replace-all': [];
  close: [];
  'update:searchText': [text: string];
}>();

const searchText = ref('');
const replaceText = ref('');
const searchInputEl = ref<HTMLInputElement | null>(null);

const matchCountText = computed(() => {
  if (!searchText.value) return '';
  if (props.matchCount === 0) return t('find.no_results');
  return `${props.activeMatchIndex + 1} / ${props.matchCount}`;
});

const canReplace = computed(() => {
  return props.matchCount > 0 && replaceText.value.length > 0;
});

let debounceTimer: ReturnType<typeof setTimeout> | null = null;

function onSearchInput() {
  if (debounceTimer) clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    emit('search', searchText.value);
  }, 200);
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    emit('next');
  } else if (e.key === 'Enter' && e.shiftKey) {
    e.preventDefault();
    emit('prev');
  } else if (e.key === 'Escape') {
    e.preventDefault();
    emit('close');
  }
}

function onReplaceKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter') {
    e.preventDefault();
    if (canReplace.value) {
      emit('replace');
    }
  }
}

watch(
  () => props.visible,
  async (v) => {
    if (v) {
      searchText.value = '';
      replaceText.value = '';
      await nextTick();
      searchInputEl.value?.focus();
    }
  }
);

defineExpose({ searchText, replaceText });
</script>

<style scoped>
@keyframes slide-in {
  from {
    opacity: 0;
    transform: translateY(-4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.animate-slide-in {
  animation: slide-in 0.15s ease-out;
}
</style>
