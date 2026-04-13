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
      class="flex-shrink-0 w-8 h-8 glass-surface rounded-xl flex items-center justify-center text-text-muted hover:text-accent-blue transition-colors duration-150"
    >
      <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
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
