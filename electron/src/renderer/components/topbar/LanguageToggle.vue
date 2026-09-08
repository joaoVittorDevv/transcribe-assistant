<template>
  <div class="flex items-center gap-0.5 bg-[#16181F] border border-[#2D3342] rounded-md p-0.5 shadow-sm">
    <button
      v-for="lang in langs"
      :key="lang"
      @click="switchLang(lang)"
      :class="[
        'px-2 py-1 rounded text-xs font-inter font-semibold transition-all duration-150',
        currentLocale === lang
          ? 'bg-[#222733] border border-[#3F444E] text-[#DDE2F6] shadow-sm'
          : 'text-[#909095] border border-transparent hover:text-[#DDE2F6] hover:bg-[#1A1D24]'
      ]"
    >
      {{ lang.toUpperCase() }}
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { setLocale, getLocale, i18nState } from '../../i18n';

const langs = ['pt', 'en'] as const;

const currentLocale = computed(() => i18nState.locale);

function switchLang(lang: 'pt' | 'en') {
  setLocale(lang);
}
</script>
