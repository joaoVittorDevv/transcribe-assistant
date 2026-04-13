<template>
  <aside class="sidebar">
    <div class="glass-surface h-full flex flex-col justify-between p-4">
      <div>
        <!-- Header: active prompt -->
        <div class="flex items-center gap-3 mb-4">
          <span class="text-accent-blue">
            <!-- Microphone icon (heroicons outline) -->
            <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z" />
            </svg>
          </span>
          <div>
            <p class="text-xs text-text-muted font-plus-jakarta font-medium">{{ t('sidebar.active_prompt') }}</p>
            <p class="text-sm text-text-primary font-plus-jakarta font-semibold">Padrão</p>
          </div>
        </div>

        <!-- Prompt list -->
        <div class="flex flex-col gap-2 mb-4">
          <div
            v-for="item in promptItems"
            :key="item"
            class="px-3 py-3 text-sm font-plus-jakarta font-medium text-text-primary cursor-pointer transition-all duration-150 rounded-xl hover:bg-white/5"
            :class="{ 'bg-accent-blue/20 border-l-2 border-accent-blue': item === activeItem }"
          >
            {{ item }}
          </div>
        </div>
      </div>

      <!-- Manage prompts button -->
      <button class="glass-btn w-full text-center text-sm py-2">
        {{ t('sidebar.manage_prompts') }}
      </button>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { t } from '../../i18n';

const promptItems = [
  'Resumos do dia',
  'Projetos Gerais',
];

const activeItem = ref('Resumos do dia');
</script>

<style scoped>
.sidebar {
  width: 20%;
  min-width: 200px;
  max-width: 260px;
  height: 100%;
  display: flex;
  flex-direction: column;
}
</style>
