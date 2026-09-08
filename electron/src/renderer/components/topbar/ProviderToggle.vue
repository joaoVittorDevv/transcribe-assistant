<template>
  <div class="flex items-center bg-[#16181F] p-0.5 rounded-lg border border-[#2D3342] shadow-sm">
    <button
      v-for="option in options"
      :key="option.value"
      @click="setProvider(option.value)"
      :class="[
        'px-2.5 h-7 rounded-md text-[11px] font-inter font-medium transition-all duration-150 cursor-pointer flex items-center justify-center',
        selectedProvider === option.value
          ? 'bg-[#222733] text-[#F59E0B] font-semibold shadow-xs'
          : 'text-[#909095] hover:text-[#DDE2F6] hover:bg-[#1A1D24]'
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
