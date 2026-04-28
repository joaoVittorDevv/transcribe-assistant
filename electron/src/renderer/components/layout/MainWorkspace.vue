<template>
  <div class="main-workspace flex flex-col flex-1 min-w-0">
    <!-- Top Utility Bar -->
    <div class="flex items-center gap-3 px-4 py-3 flex-shrink-0 glass-surface">
      <ProviderToggle />
      <div class="flex-1"></div>
      <NetworkStatus />
      <LanguageToggle />
      <TopActionButtons @open-settings="showSettings = true" />
    </div>

    <!-- Tab Bar -->
    <div class="flex-shrink-0 px-2">
      <TabBar />
    </div>

    <!-- Editor area -->
    <div class="flex-1 min-h-0 px-4 py-2 flex flex-col">
      <TextEditor />
    </div>

    <!-- Bottom Control Bar -->
    <div class="flex-shrink-0">
      <BottomActionBar />
    </div>

    <!-- Prompt Settings Modal -->
    <PromptModal :visible="showSettings" @close="showSettings = false" />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import ProviderToggle from '../topbar/ProviderToggle.vue';
import NetworkStatus from '../topbar/NetworkStatus.vue';
import LanguageToggle from '../topbar/LanguageToggle.vue';
import TopActionButtons from '../topbar/TopActionButtons.vue';
import TabBar from '../tabs/TabBar.vue';
import TextEditor from '../editor/TextEditor.vue';
import BottomActionBar from '../bottom/BottomActionBar.vue';
import PromptModal from '../prompt/PromptModal.vue';

const showSettings = ref(false);
</script>

<style scoped>
.main-workspace {
  height: 100%;
}
</style>
