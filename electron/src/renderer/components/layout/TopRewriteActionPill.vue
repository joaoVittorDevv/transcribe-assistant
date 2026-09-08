<template>
  <div class="top-rewrite-action flex items-center gap-1.5 relative z-40 select-none font-inter">
    <!-- Grouped Capsule for Agent Selector & Rewrite Action -->
    <div class="flex items-center bg-[#16181F] p-0.5 rounded-lg border border-[#2D3342] shadow-sm">
      <!-- Agent Selector Dropdown Button -->
      <div class="relative z-50" ref="dropdownRef">
        <button
          type="button"
          @click="dropdownOpen = !dropdownOpen"
          :class="[
            'flex items-center gap-1.5 px-2.5 h-7 rounded-md text-xs font-medium transition-all duration-150',
            dropdownOpen
              ? 'bg-[#222733] text-[#DDE2F6]'
              : 'text-[#909095] hover:text-[#DDE2F6] hover:bg-[#1A1D24]'
          ]"
          title="Selecionar Agente de Reescrita"
        >
          <span class="text-xs">{{ activeAgent?.icon || '✨' }}</span>
          <span class="max-w-[130px] truncate text-[11px] font-semibold text-[#DDE2F6]">
            {{ activeAgent?.name || 'Agente IA' }}
          </span>
          <svg
            :class="['w-3 h-3 text-[#909095] transition-transform duration-150', dropdownOpen ? 'rotate-180' : '']"
            fill="none" stroke="currentColor" viewBox="0 0 24 24"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        <!-- Dropdown Menu List -->
        <div
          v-if="dropdownOpen"
          class="absolute left-0 mt-2 w-64 bg-[#16181F] border border-[#2D3342] rounded-xl shadow-2xl z-50 py-1.5 animate-slide-in overflow-hidden"
        >
          <div class="px-3 py-1 text-[10px] uppercase font-bold tracking-wider text-[#909095] border-b border-[#2D3342] flex items-center justify-between">
            <span>Agentes de Reescrita</span>
            <span class="font-mono text-[#DDE2F6]">{{ agents.length }}</span>
          </div>

          <div class="max-h-56 overflow-y-auto py-1">
            <button
              v-for="agent in agents"
              :key="agent.id"
              type="button"
              @click="selectAgent(agent.id)"
              :class="[
                'w-full px-3 py-2 text-left flex items-start gap-2.5 hover:bg-[#222733] transition-colors',
                agent.id === activeAgent?.id ? 'bg-[#222733]/60 text-[#3B82F6]' : 'text-[#DDE2F6]'
              ]"
            >
              <span class="text-base flex-shrink-0 mt-0.5">{{ agent.icon }}</span>
              <div class="flex-1 min-w-0">
                <div class="flex items-center justify-between">
                  <span class="text-xs font-semibold truncate">{{ agent.name }}</span>
                  <div class="flex items-center gap-1">
                    <span v-if="agent.agent_type === 'multi-check'" class="text-[8.5px] px-1 py-0.2 rounded bg-[#10B981]/20 text-[#34D399] border border-[#10B981]/30 font-mono">
                      multi-check
                    </span>
                    <span v-if="Boolean(agent.is_default)" class="text-[8.5px] px-1 py-0.2 rounded bg-[#3B82F6]/20 text-[#60A5FA] border border-[#3B82F6]/30 font-mono">
                      padrão
                    </span>
                  </div>
                </div>
                <p class="text-[10px] text-[#909095] truncate mt-0.5">{{ agent.description || agent.tone }}</p>
              </div>
              <svg
                v-if="agent.id === activeAgent?.id"
                class="w-3.5 h-3.5 text-[#3B82F6] flex-shrink-0 mt-1"
                fill="none" stroke="currentColor" viewBox="0 0 24 24"
              >
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7" />
              </svg>
            </button>
          </div>

          <div class="border-t border-[#2D3342] px-2 pt-1.5">
            <button
              type="button"
              @click="openSettingsAgents"
              class="w-full py-1.5 text-center text-[11px] font-medium text-[#F59E0B] hover:bg-[#F59E0B]/10 rounded-md transition-colors flex items-center justify-center gap-1 cursor-pointer"
            >
              <span>+ Gerenciar / Criar com IA</span>
            </button>
          </div>
        </div>
      </div>

      <!-- Subtle separator -->
      <div class="h-3.5 w-px bg-[#2D3342] mx-0.5"></div>

      <!-- Rewrite Trigger Button -->
      <button
        type="button"
        @click="triggerRewrite"
        :disabled="rewriting || !hasContent"
        :class="[
          'flex items-center gap-1.5 px-3 h-7 rounded-md text-[11.5px] font-semibold transition-all duration-150 font-inter',
          rewriting
            ? 'bg-[#3B82F6]/20 text-[#60A5FA] cursor-wait'
            : hasContent
              ? 'bg-[#2563EB] hover:bg-[#1D4ED8] text-white shadow-xs hover:shadow cursor-pointer'
              : 'text-[#909095]/40 cursor-not-allowed'
        ]"
        title="Reestruturar texto com o Agente selecionado (Ctrl+Shift+R)"
      >
        <svg
          v-if="rewriting"
          class="animate-spin h-3.5 w-3.5 text-[#60A5FA]"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        <svg
          v-else
          class="w-3.5 h-3.5"
          fill="none" stroke="currentColor" viewBox="0 0 24 24"
        >
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
        </svg>
        <span>{{ rewriting ? 'Reestruturando...' : 'Reestruturar' }}</span>
      </button>
    </div>

    <!-- Multi-Check Iterative Review Modal -->
    <MultiCheckReviewModal
      :visible="multiCheckModalOpen"
      :agent="activeAgent"
      :original-text="multiCheckOriginalText"
      @approve="handleMultiCheckApprove"
      @reject="handleMultiCheckReject"
      @close="multiCheckModalOpen = false"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { useRewriteAgents } from '../../composables/useRewriteAgents';
import { useTabs } from '../../composables/useTabs';
import { useEditor } from '../../composables/useEditor';
import MultiCheckReviewModal from '../editor/MultiCheckReviewModal.vue';

const emit = defineEmits<{
  'open-settings': [tab: string];
}>();

const { agents, activeAgent, rewriting, fetchAgents, setActiveAgentId, executeRewriteStream } = useRewriteAgents();
const { activeTabId, getActiveTab, updateContent } = useTabs();
const { getMarkdown } = useEditor();

const dropdownOpen = ref(false);
const dropdownRef = ref<HTMLElement | null>(null);

const multiCheckModalOpen = ref(false);
const multiCheckOriginalText = ref('');

const hasContent = computed(() => {
  const tab = getActiveTab();
  const text = tab?.content || getMarkdown();
  return Boolean(text && text.trim().length > 0);
});

function selectAgent(id: number) {
  setActiveAgentId(id);
  dropdownOpen.value = false;
}

function openSettingsAgents() {
  dropdownOpen.value = false;
  emit('open-settings', 'agents');
}

async function triggerRewrite() {
  if (rewriting.value) return;
  const currentTab = getActiveTab();
  const rawText = currentTab?.content || getMarkdown();
  if (!rawText || !rawText.trim()) return;

  // Check if active agent is Multi-Check
  if (activeAgent.value?.agent_type === 'multi-check') {
    multiCheckOriginalText.value = rawText;
    multiCheckModalOpen.value = true;
    return;
  }

  // Otherwise (no-check mode): execute direct streaming into editor
  try {
    const result = await executeRewriteStream(rawText, (accumulated) => {
      if (activeTabId.value) {
        updateContent(activeTabId.value, accumulated);
      }
    });
    if (result && activeTabId.value) {
      updateContent(activeTabId.value, result);
    }
  } catch (err) {
    console.error('Erro na reestruturação:', err);
  }
}

function handleMultiCheckApprove(finalText: string) {
  if (activeTabId.value && finalText) {
    updateContent(activeTabId.value, finalText);
  }
}

function handleMultiCheckReject() {
  // Discard draft, leaving active tab text 100% untouched!
}

function handleGlobalKeydown(e: KeyboardEvent) {
  // Ctrl+Shift+R shortcut for instant rewrite
  if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === 'r') {
    e.preventDefault();
    triggerRewrite();
  }
}

function handleClickOutside(event: MouseEvent) {
  if (dropdownRef.value && !dropdownRef.value.contains(event.target as Node)) {
    dropdownOpen.value = false;
  }
}

onMounted(() => {
  fetchAgents();
  document.addEventListener('click', handleClickOutside);
  document.addEventListener('keydown', handleGlobalKeydown);
});

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside);
  document.removeEventListener('keydown', handleGlobalKeydown);
});
</script>

<style scoped>
@keyframes slide-in {
  from {
    opacity: 0;
    transform: translateY(-4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.animate-slide-in {
  animation: slide-in 0.15s ease-out;
}
</style>
