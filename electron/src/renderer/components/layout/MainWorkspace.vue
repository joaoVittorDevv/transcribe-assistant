<template>
  <div class="main-workspace flex flex-col flex-1 min-w-0 h-full overflow-hidden bg-[#13151A]">
    <!-- Top Command Bar -->
    <header class="relative z-30 flex items-center justify-between gap-3 px-4 py-2 flex-shrink-0 bg-[#16181F]/90 backdrop-blur-md border-b border-[#2D3342] h-12 select-none">
      <!-- Left: Minimalist App Brand -->
      <div class="flex items-center gap-2 flex-shrink-0">
        <div class="w-6 h-6 rounded-md bg-[#F59E0B]/10 border border-[#F59E0B]/30 flex items-center justify-center text-[#F59E0B] shadow-xs">
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
          </svg>
        </div>
        <span class="text-xs font-bold text-[#E5E7EB] tracking-tight font-inter">Transcribe</span>
      </div>

      <!-- Center: Rewrite Action Pill & Provider Toggle -->
      <div class="flex items-center gap-2.5 relative z-30">
        <TopRewriteActionPill @open-settings="openSettingsModal" />
        <div class="h-3.5 w-px bg-[#2D3342]"></div>
        <ProviderToggle />
      </div>

      <!-- Right: Actions & Minimal Network Status Beacon -->
      <div class="flex items-center gap-2 relative z-30">
        <TopActionButtons @open-settings="openSettingsModal('prompt')" />
        <div class="h-3.5 w-px bg-[#2D3342]"></div>
        <NetworkStatus />
      </div>
    </header>

    <!-- Session Tabs Bar -->
    <div class="flex-shrink-0 px-3 pt-2 relative z-10">
      <TabBar />
    </div>

    <!-- Editor Bento Canvas Area -->
    <main class="flex-1 min-h-0 px-3 py-2 flex flex-col overflow-hidden relative z-0">
      <TextEditor />
    </main>

    <!-- Studio Control Capsule (Bottom Action Dock) -->
    <footer class="flex-shrink-0">
      <BottomActionBar />
    </footer>

    <!-- Settings Modal (Bento Grid) -->
    <SettingsModal
      :visible="showSettings"
      :initial-tab="settingsInitialTab"
      @close="showSettings = false"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import TopRewriteActionPill from './TopRewriteActionPill.vue';
import ProviderToggle from '../topbar/ProviderToggle.vue';
import NetworkStatus from '../topbar/NetworkStatus.vue';
import TopActionButtons from '../topbar/TopActionButtons.vue';
import TabBar from '../tabs/TabBar.vue';
import TextEditor from '../editor/TextEditor.vue';
import BottomActionBar from '../bottom/BottomActionBar.vue';
import SettingsModal from '../settings/SettingsModal.vue';

const showSettings = ref(false);
const settingsInitialTab = ref<'prompt' | 'providers' | 'agents' | 'storage' | 'tray' | 'network'>('prompt');

function openSettingsModal(tab: 'prompt' | 'providers' | 'agents' | 'storage' | 'tray' | 'network' = 'prompt') {
  settingsInitialTab.value = tab;
  showSettings.value = true;
}

onMounted(async () => {
  // Sync electron tray configurations at boot
  try {
    const res = await fetch('http://localhost:18763/settings');
    if (res.ok) {
      const data = await res.json();
      if (window.electronAPI && window.electronAPI.updateSettingsTray) {
        window.electronAPI.updateSettingsTray({
          enabled: data.tray_enabled ?? false,
          notificationsEnabled: data.persistent_notifications_enabled ?? true,
          interval: data.alert_interval ?? 15,
          types: data.alert_transcription_types || 'realtime'
        });
      }
    }
  } catch (err) {
    console.warn('Failed to load settings at boot to sync tray:', err);
  }
});
</script>

<style scoped>
.main-workspace {
  height: 100vh;
  width: 100vw;
}
</style>
