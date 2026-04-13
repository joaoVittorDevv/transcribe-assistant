<template>
  <div class="flex items-center gap-1.5 px-3 py-1.5 glass-surface rounded-xl">
    <span :class="['h-2 w-2 rounded-full', isOnline ? 'bg-accent-green' : 'bg-yellow-500']"></span>
    <span class="text-xs font-plus-jakarta font-medium text-text-muted">
      {{ isOnline ? t('network.online') : t('network.offline') }}
    </span>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import { t } from '../../i18n';

const isOnline = ref(navigator.onLine);

function handleOnline() { isOnline.value = true; }
function handleOffline() { isOnline.value = false; }

onMounted(() => {
  window.addEventListener('online', handleOnline);
  window.addEventListener('offline', handleOffline);
});

onUnmounted(() => {
  window.removeEventListener('online', handleOnline);
  window.removeEventListener('offline', handleOffline);
});
</script>
