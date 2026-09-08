<template>
  <div
    class="relative flex items-center justify-center w-6 h-6 cursor-default"
    :title="isOnline ? 'Online • Sistema conectado' : 'Offline • Sem conexão'"
  >
    <span
      v-if="isOnline"
      class="absolute inline-flex h-2 w-2 rounded-full bg-[#10B981] opacity-70 animate-ping"
    ></span>
    <span
      :class="[
        'relative inline-flex h-2 w-2 rounded-full transition-all duration-300',
        isOnline
          ? 'bg-[#10B981] shadow-[0_0_8px_rgba(16,185,129,0.9)]'
          : 'bg-[#EF4444] shadow-[0_0_8px_rgba(239,68,68,0.9)]'
      ]"
    ></span>
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
