<template>
  <aside
    :class="[
      'flex flex-col border-r border-[#2D3342] bg-[#16181F] transition-all duration-200 ease-in-out select-none relative z-20 flex-shrink-0',
      collapsed ? 'w-16' : 'w-56'
    ]"
  >
    <!-- Brand / Header -->
    <div class="flex items-center justify-between px-3.5 py-4 border-b border-[#2D3342] h-14">
      <div v-if="!collapsed" class="flex items-center gap-2.5 overflow-hidden">
        <div class="w-7 h-7 rounded-lg bg-[#222733] border border-[#3F444E] flex items-center justify-center flex-shrink-0 shadow-sm">
          <svg class="w-4 h-4 text-[#F59E0B]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
          </svg>
        </div>
        <div class="flex flex-col">
          <span class="text-xs font-bold text-[#DDE2F6] tracking-tight leading-none font-inter">Transcribe</span>
          <span class="text-[10px] text-[#909095] font-medium leading-tight">Studio Precision</span>
        </div>
      </div>
      <div v-else class="w-full flex justify-center">
        <div class="w-7 h-7 rounded-lg bg-[#222733] border border-[#3F444E] flex items-center justify-center shadow-sm">
          <svg class="w-4 h-4 text-[#F59E0B]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
          </svg>
        </div>
      </div>

      <button
        @click="collapsed = !collapsed"
        class="text-[#909095] hover:text-[#DDE2F6] p-1 rounded hover:bg-[#222733] transition-colors"
        :title="collapsed ? 'Expandir Sidebar' : 'Recolher Sidebar'"
      >
        <svg v-if="!collapsed" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
        </svg>
        <svg v-else class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 5l7 7-7 7M5 5l7 7-7 7" />
        </svg>
      </button>
    </div>

    <!-- Navigation List -->
    <nav class="flex-1 py-3 px-2 flex flex-col gap-1 overflow-y-auto">
      <button
        @click="$emit('nav', 'editor')"
        :class="[
          'flex items-center gap-2.5 px-2.5 py-2 rounded-md text-xs font-medium transition-colors w-full text-left',
          activeView === 'editor'
            ? 'bg-[#222733] text-[#F59E0B] border border-[#3F444E]/60 shadow-sm'
            : 'text-[#909095] hover:text-[#DDE2F6] hover:bg-[#1A1D24]'
        ]"
      >
        <svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.75" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
        </svg>
        <span v-if="!collapsed" class="truncate font-inter">Editor & Transcrição</span>
      </button>

      <button
        @click="$emit('open-prompts')"
        class="flex items-center gap-2.5 px-2.5 py-2 rounded-md text-xs font-medium text-[#909095] hover:text-[#DDE2F6] hover:bg-[#1A1D24] transition-colors w-full text-left"
        title="Prompt & Glossário"
      >
        <svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.75" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
        </svg>
        <span v-if="!collapsed" class="truncate font-inter">Prompts & Glossário</span>
      </button>

      <button
        @click="$emit('open-history')"
        class="flex items-center gap-2.5 px-2.5 py-2 rounded-md text-xs font-medium text-[#909095] hover:text-[#DDE2F6] hover:bg-[#1A1D24] transition-colors w-full text-left"
        title="Histórico de Sessões"
      >
        <svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.75" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <span v-if="!collapsed" class="truncate font-inter">Histórico Salvo</span>
      </button>

      <button
        @click="$emit('open-settings')"
        class="flex items-center gap-2.5 px-2.5 py-2 rounded-md text-xs font-medium text-[#909095] hover:text-[#DDE2F6] hover:bg-[#1A1D24] transition-colors w-full text-left"
        title="Configurações Gerais"
      >
        <svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.75" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.75" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
        <span v-if="!collapsed" class="truncate font-inter">Configurações</span>
      </button>
    </nav>

    <!-- Bottom Metrics Widget -->
    <div class="p-2.5 border-t border-[#2D3342] flex flex-col gap-2">
      <div v-if="!collapsed" class="bg-[#1A1D24] p-2.5 rounded-md border border-[#2D3342] flex flex-col gap-1.5">
        <div class="flex items-center justify-between text-[10px] text-[#909095]">
          <span class="font-medium">Storage Vault</span>
          <span class="text-[#DDE2F6] font-mono">1.2 GB</span>
        </div>
        <div class="w-full bg-[#13151A] h-1.5 rounded-full overflow-hidden border border-[#2D3342]/60">
          <div class="bg-[#3B82F6] h-full rounded-full" style="width: 24%"></div>
        </div>
      </div>

      <div class="flex items-center justify-between px-1 text-[11px] text-[#909095]">
        <div class="flex items-center gap-1.5">
          <span class="w-2 h-2 rounded-full bg-[#10B981] animate-pulse"></span>
          <span v-if="!collapsed" class="font-mono text-[10px] text-[#DDE2F6]">32ms</span>
        </div>
        <span v-if="!collapsed" class="text-[10px] text-[#909095]">v0.2.0</span>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { ref } from 'vue';

const collapsed = ref(false);
const activeView = ref<'editor' | 'history'>('editor');

defineEmits<{
  (e: 'nav', view: 'editor' | 'history'): void;
  (e: 'open-settings'): void;
  (e: 'open-prompts'): void;
  (e: 'open-history'): void;
}>();
</script>
