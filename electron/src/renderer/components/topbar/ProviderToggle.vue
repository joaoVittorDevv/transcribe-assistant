<template>
  <div class="flex items-center gap-1 glass-surface rounded-xl p-1">
    <button
      v-for="option in options"
      :key="option.value"
      @click="selected = option.value"
      :class="[
        'px-3 py-1.5 rounded-xl text-xs font-plus-jakarta font-semibold transition-all duration-150',
        selected === option.value
          ? 'bg-accent-blue/20 text-accent-blue'
          : 'text-text-muted hover:text-text-primary'
      ]"
    >
      {{ option.label }}
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { t } from '../../i18n';

const selected = ref<'auto' | 'google' | 'whisper'>('auto');

const options = [
  { value: 'auto' as const, label: t('provider.auto') },
  { value: 'google' as const, label: t('provider.google') },
  { value: 'whisper' as const, label: t('provider.whisper') },
];
</script>
