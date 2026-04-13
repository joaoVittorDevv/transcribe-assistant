<template>
  <div class="main-workspace flex flex-col flex-1 min-w-0">
    <!-- Top Utility Bar -->
    <div class="flex items-center gap-3 px-4 py-3 flex-shrink-0 glass-surface">
      <ProviderToggle />
      <div class="flex-1"></div>
      <NetworkStatus />
      <LanguageToggle />
      <TopActionButtons />
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
  </div>
</template>

<script setup lang="ts">
import ProviderToggle from '../topbar/ProviderToggle.vue';
import NetworkStatus from '../topbar/NetworkStatus.vue';
import LanguageToggle from '../topbar/LanguageToggle.vue';
import TopActionButtons from '../topbar/TopActionButtons.vue';
import TabBar from '../tabs/TabBar.vue';
import TextEditor from '../editor/TextEditor.vue';
import BottomActionBar from '../bottom/BottomActionBar.vue';
</script>

<style scoped>
.main-workspace {
  height: 100%;
}
</style>
