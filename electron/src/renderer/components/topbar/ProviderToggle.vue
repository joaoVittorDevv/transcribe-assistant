<template>
  <div class="flex items-center gap-1 glass-surface rounded-xl p-1">
    <button
      v-for="option in options"
      :key="option.value"
      @click="setProvider(option.value)"
      :class="[
        'px-3 py-1.5 rounded-xl text-xs font-plus-jakarta font-semibold transition-all duration-150',
        selectedProvider === option.value
          ? 'bg-accent-blue/20 text-accent-blue'
          : 'text-text-muted hover:text-text-primary'
      ]"
    >
      {{ option.label }}
    </button>
  </div>
</template>

<script setup lang="ts">
import { useProvider } from '../../composables/useProvider';
import { t } from '../../i18n';

const { selectedProvider, setProvider } = useProvider();

const options = [
  { value: 'auto' as const, label: t('provider.auto') },
  { value: 'google' as const, label: t('provider.google') },
  { value: 'groq' as const, label: t('provider.groq') },
];
</script>
