<template>
  <div class="flex items-center gap-1 glass-surface rounded-xl p-1">
    <button
      v-for="lang in langs"
      :key="lang"
      @click="switchLang(lang)"
      :class="[
        'px-2.5 py-1 rounded-xl text-xs font-plus-jakarta font-semibold transition-all duration-150',
        currentLocale === lang
          ? 'bg-accent-blue/20 text-accent-blue'
          : 'text-text-muted hover:text-text-primary'
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
