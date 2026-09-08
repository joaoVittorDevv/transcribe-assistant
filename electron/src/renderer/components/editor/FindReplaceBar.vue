<template>
  <div
    v-if="visible"
    class="find-replace-bar bg-[#1A1D24] border border-[#2D3342] flex flex-col gap-2 p-2.5 rounded-md mb-2 shadow-xl animate-slide-in font-inter select-none"
  >
    <!-- Search row -->
    <div class="flex items-center gap-2">
      <div class="flex-1 relative">
        <svg
          class="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[#909095]"
          fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"
        >
          <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
        </svg>
        <input
          ref="searchInputEl"
          v-model="searchText"
          type="text"
          :placeholder="t('find.search_placeholder')"
          class="w-full bg-[#13151A] border border-[#2D3342] rounded py-1 pl-8 pr-14 text-xs text-[#DDE2F6] placeholder-[#909095]/60 focus:outline-none focus:border-[#3B82F6] focus:ring-1 focus:ring-[#3B82F6]/30 font-inter"
          @input="onSearchInput"
          @keydown="onKeydown"
        />

        <!-- In-input toggle: Case Sensitive (Aa) -->
        <button
          type="button"
          @click="toggleCaseSensitive"
          :class="[
            'absolute right-1.5 top-1/2 -translate-y-1/2 px-1.5 py-0.5 rounded text-[10px] font-mono font-bold transition-colors',
            caseSensitive
              ? 'bg-[#3B82F6] text-white'
              : 'text-[#909095] hover:text-[#DDE2F6] hover:bg-[#222733]'
          ]"
          title="Diferenciar maiúsculas/minúsculas (Aa)"
        >
          Aa
        </button>
      </div>

      <!-- Match Counter -->
      <span class="text-[11px] text-[#909095] min-w-[54px] text-right font-mono tabular-nums">
        {{ matchCountText }}
      </span>

      <!-- Match Navigation (Previous / Next) -->
      <button
        type="button"
        class="p-1 rounded hover:bg-[#222733] text-[#909095] hover:text-[#DDE2F6] border border-transparent hover:border-[#2D3342] transition-colors"
        :title="`${t('find.previous')} (Shift+Enter)`"
        @click="$emit('prev')"
      >
        <svg class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M5 15l7-7 7 7" />
        </svg>
      </button>
      <button
        type="button"
        class="p-1 rounded hover:bg-[#222733] text-[#909095] hover:text-[#DDE2F6] border border-transparent hover:border-[#2D3342] transition-colors"
        :title="`${t('find.next')} (Enter)`"
        @click="$emit('next')"
      >
        <svg class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      <!-- Close Button -->
      <button
        type="button"
        class="p-1 rounded hover:bg-[#222733] text-[#909095] hover:text-[#EF4444] border border-transparent hover:border-[#2D3342] transition-colors"
        :title="`${t('find.close')} (Esc)`"
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
          ref="replaceInputEl"
          v-model="replaceText"
          type="text"
          :placeholder="t('find.replace_placeholder')"
          class="w-full bg-[#13151A] border border-[#2D3342] rounded py-1 px-3 text-xs text-[#DDE2F6] placeholder-[#909095]/60 focus:outline-none focus:border-[#3B82F6] focus:ring-1 focus:ring-[#3B82F6]/30 font-inter"
          @keydown="onReplaceKeydown"
        />
      </div>
      <button
        type="button"
        class="px-2.5 py-1 text-xs font-medium rounded bg-[#222733] border border-[#2D3342] text-[#DDE2F6] hover:bg-[#2A303F] hover:border-[#3F444E] transition-colors disabled:opacity-30 disabled:cursor-not-allowed font-inter"
        :disabled="!canReplace"
        @click="$emit('replace')"
      >
        {{ t('find.replace') }}
      </button>
      <button
        type="button"
        class="px-2.5 py-1 text-xs font-semibold rounded bg-[#3B82F6]/15 border border-[#3B82F6]/40 text-[#60A5FA] hover:bg-[#3B82F6]/25 transition-colors disabled:opacity-30 disabled:cursor-not-allowed font-inter"
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
  initialMode?: 'find' | 'replace';
}>();

const emit = defineEmits<{
  search: [text: string, caseSensitive: boolean];
  next: [];
  prev: [];
  replace: [];
  'replace-all': [];
  close: [];
  'update:caseSensitive': [value: boolean];
}>();

const searchText = ref('');
const replaceText = ref('');
const caseSensitive = ref(false);
const searchInputEl = ref<HTMLInputElement | null>(null);
const replaceInputEl = ref<HTMLInputElement | null>(null);

const matchCountText = computed(() => {
  if (!searchText.value) return '';
  if (props.matchCount === 0) return t('find.no_results');
  return `${props.activeMatchIndex + 1} / ${props.matchCount}`;
});

const canReplace = computed(() => {
  return props.matchCount > 0 && replaceText.value.length > 0;
});

let debounceTimer: ReturnType<typeof setTimeout> | null = null;

function triggerSearch() {
  emit('search', searchText.value, caseSensitive.value);
}

function onSearchInput() {
  if (debounceTimer) clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    triggerSearch();
  }, 150);
}

function toggleCaseSensitive() {
  caseSensitive.value = !caseSensitive.value;
  emit('update:caseSensitive', caseSensitive.value);
  triggerSearch();
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
  } else if (e.key === 'Escape') {
    e.preventDefault();
    emit('close');
  }
}

watch(
  () => props.visible,
  async (v) => {
    if (v) {
      await nextTick();
      if (props.initialMode === 'replace') {
        replaceInputEl.value?.focus();
      } else {
        searchInputEl.value?.focus();
        searchInputEl.value?.select();
      }
    }
  }
);

defineExpose({
  searchText,
  replaceText,
  caseSensitive,
  focusSearch: () => searchInputEl.value?.focus(),
  focusReplace: () => replaceInputEl.value?.focus(),
});
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
