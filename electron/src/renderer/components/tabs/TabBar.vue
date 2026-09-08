<template>
  <div class="flex items-center gap-2 px-2 py-2 overflow-x-auto">
    <TabItem
      v-for="tab in tabs"
      :key="tab.id"
      :tab="tab"
      :is-active="tab.id === activeTabId"
      :can-close="tabs.length > 1"
      @activate="setActive(tab.id)"
      @close="closeTab(tab.id)"
    />
    <!-- Add tab button -->
    <button
      @click="addTab"
      class="flex-shrink-0 w-7 h-7 bg-[#1A1D24] border border-[#2D3342] hover:border-[#3F444E] rounded-md flex items-center justify-center text-[#909095] hover:text-[#F59E0B] transition-colors duration-150"
      title="Nova Sessão"
    >
      <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
        <path fill-rule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" clip-rule="evenodd" />
      </svg>
    </button>
  </div>
</template>

<script setup lang="ts">
import TabItem from './TabItem.vue';
import { useTabs } from '../../composables/useTabs';

const { tabs, activeTabId, addTab, closeTab, setActive } = useTabs();
</script>
