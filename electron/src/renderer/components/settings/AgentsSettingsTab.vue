<template>
  <div class="agents-settings-tab flex flex-col gap-4 font-inter">
    <!-- Header with Actions -->
    <div class="flex items-center justify-between border-b border-[#2D3342] pb-3">
      <div>
        <h3 class="text-xs font-bold text-[#DDE2F6]">Agentes de Reescrita &amp; Reestruturação</h3>
        <p class="text-[10px] text-[#909095]">Configure e crie assistentes com o Meta-Agente da MiniMax</p>
      </div>

      <div class="flex items-center gap-2">
        <button
          type="button"
          @click="openAIModal"
          class="bento-btn py-1.5 px-3 text-xs flex items-center gap-1.5 text-[#10B981] hover:text-[#34D399] border-[#10B981]/30 hover:bg-[#10B981]/10 font-semibold"
        >
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          <span>Criar com IA (MiniMax)</span>
        </button>

        <button
          type="button"
          @click="openManualCreate"
          class="bento-btn py-1.5 px-3 text-xs flex items-center gap-1.5 text-[#DDE2F6]"
        >
          <span>+ Novo Manual</span>
        </button>
      </div>
    </div>

    <!-- Error Alert if any -->
    <div v-if="error" class="p-2.5 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-xs flex items-center justify-between">
      <span>{{ error }}</span>
      <button @click="error = null" class="text-red-400 hover:text-red-200 ml-2">&times;</button>
    </div>

    <!-- Loading State -->
    <div v-if="loading && agents.length === 0" class="py-8 text-center text-xs text-[#909095]">
      <svg class="animate-spin h-5 w-5 text-[#F59E0B] mx-auto mb-2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
      </svg>
      <span>Carregando catálogo de agentes...</span>
    </div>

    <!-- Agents Grid -->
    <div v-else class="grid grid-cols-1 gap-3">
      <div
        v-for="agent in agents"
        :key="agent.id"
        class="bento-card p-4 flex flex-col gap-3 transition-all duration-150 hover:border-[#3F444E]"
      >
        <!-- Card Header -->
        <div class="flex items-start justify-between gap-2">
          <div class="flex items-center gap-2.5">
            <span class="text-xl p-1.5 rounded-lg bg-[#222733] border border-[#3F444E] flex items-center justify-center">{{ agent.icon || '✨' }}</span>
            <div>
              <div class="flex items-center gap-2">
                <span class="text-xs font-bold text-[#DDE2F6]">{{ agent.name }}</span>
                <span v-if="Boolean(agent.is_default)" class="px-1.5 py-0.2 rounded text-[9.5px] font-mono bg-[#3B82F6]/20 text-[#60A5FA] border border-[#3B82F6]/30 font-semibold">
                  ★ Padrão
                </span>
              </div>
              <p class="text-[11px] text-[#909095] mt-0.5">{{ agent.description }}</p>
            </div>
          </div>

          <!-- Card Actions -->
          <div class="flex items-center gap-1.5">
            <button
              v-if="!Boolean(agent.is_default)"
              type="button"
              @click="setDefaultAgent(agent.id)"
              class="px-2 py-1 rounded text-[10.5px] bg-[#222733] text-[#909095] hover:text-[#F59E0B] border border-[#3F444E] transition-colors"
              title="Definir como agente padrão"
            >
              Tornar Padrão
            </button>

            <button
              type="button"
              @click="openAIEdit(agent)"
              class="px-2 py-1 rounded text-[10.5px] bg-[#10B981]/15 text-[#34D399] hover:bg-[#10B981]/25 border border-[#10B981]/30 transition-colors flex items-center gap-1 font-semibold cursor-pointer"
              title="Aperfeiçoar este agente conversando com o Arquiteto IA"
            >
              <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              <span>Editar com IA</span>
            </button>

            <button
              type="button"
              @click="openEditModal(agent)"
              class="p-1 rounded text-[#909095] hover:text-[#DDE2F6] hover:bg-[#222733] transition-colors"
              title="Edição Manual de Parâmetros"
            >
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
              </svg>
            </button>
            <button
              v-if="agents.length > 1"
              type="button"
              @click="handleDelete(agent.id)"
              class="p-1 rounded text-[#909095] hover:text-[#EF4444] hover:bg-[#222733] transition-colors"
              title="Excluir agente"
            >
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          </div>
        </div>

        <!-- Tags / Badges -->
        <div class="flex flex-wrap items-center gap-1.5 text-[10px] font-mono text-[#909095]">
          <span
            :class="[
              'px-2 py-0.5 rounded border text-[10px] font-mono',
              agent.agent_type === 'multi-check'
                ? 'bg-[#10B981]/15 text-[#34D399] border-[#10B981]/30 font-semibold'
                : 'bg-[#3B82F6]/15 text-[#60A5FA] border-[#3B82F6]/30 font-semibold'
            ]"
          >
            {{ agent.agent_type === 'multi-check' ? '🛡️ Multi-Check (Aprovação Iterativa)' : '⚡ No-Check (Direto)' }}
          </span>
          <span class="px-2 py-0.5 rounded bg-[#13151A] border border-[#2D3342]">
            Tom: <strong class="text-[#DDE2F6]">{{ agent.tone }}</strong>
          </span>
          <span class="px-2 py-0.5 rounded bg-[#13151A] border border-[#2D3342]">
            Público: <strong class="text-[#DDE2F6]">{{ agent.target_audience }}</strong>
          </span>
          <span class="px-2 py-0.5 rounded bg-[#13151A] border border-[#2D3342]">
            Formato: <strong class="text-[#DDE2F6]">{{ agent.output_format }}</strong>
          </span>
          <span class="px-2 py-0.5 rounded bg-[#13151A] border border-[#2D3342] text-[#10B981]">
            ⚡ {{ agent.model }}
          </span>
        </div>
      </div>
    </div>

    <!-- AI Conversational Wizard Modal (Agno + MiniMax) -->
    <MetaAgentChatModal
      :visible="aiModalOpen"
      :editing-agent="editingAIAgent"
      @close="handleCloseAIModal"
      @agent-saved="fetchAgents"
      @edit-agent="handleEditFromAI"
    />

    <!-- Agent Edit / Review Modal -->
    <Teleport to="body">
      <div
        v-if="editModalOpen"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 select-none font-inter"
        @click.self="editModalOpen = false"
      >
        <div class="bg-[#16181F] border border-[#2D3342] rounded-xl w-full max-w-2xl max-h-[85vh] p-5 shadow-2xl animate-slide-in flex flex-col gap-4 overflow-hidden">
          <!-- Header -->
          <div class="flex items-center justify-between border-b border-[#2D3342] pb-3 flex-shrink-0">
            <div class="flex items-center gap-2">
              <span class="text-xl p-1 rounded bg-[#222733] border border-[#3F444E]">{{ editForm.icon || '✨' }}</span>
              <div>
                <h3 class="text-xs font-bold text-[#DDE2F6]">
                  {{ editForm.id ? 'Editar Agente de Reescrita' : 'Novo Agente de Reescrita' }}
                </h3>
                <p class="text-[10px] text-[#909095]">Ajuste fino de diretrizes e templates</p>
              </div>
            </div>
            <button @click="editModalOpen = false" class="text-[#909095] hover:text-[#DDE2F6] p-1 rounded hover:bg-[#222733]">
              &times;
            </button>
          </div>

          <!-- Form Body -->
          <div class="flex-1 overflow-y-auto pr-1 flex flex-col gap-3 text-xs select-text">
            <!-- Row 1: Icon, Name, Slug -->
            <div class="grid grid-cols-12 gap-3">
              <div class="col-span-2">
                <label class="block text-[11px] text-[#909095] font-medium mb-1">Ícone</label>
                <input
                  v-model="editForm.icon"
                  type="text"
                  class="bento-input w-full text-center py-1.5 text-base"
                />
              </div>
              <div class="col-span-6">
                <label class="block text-[11px] text-[#909095] font-medium mb-1">Nome do Agente</label>
                <input
                  v-model="editForm.name"
                  type="text"
                  class="bento-input w-full py-1.5 px-3"
                  placeholder="Ex: Mensagem Direta p/ Gestão"
                />
              </div>
              <div class="col-span-4">
                <label class="block text-[11px] text-[#909095] font-medium mb-1">Slug</label>
                <input
                  v-model="editForm.slug"
                  type="text"
                  class="bento-input w-full py-1.5 px-3 font-mono text-[11px]"
                  placeholder="mensagem-gestao"
                />
              </div>
            </div>

            <!-- Description & Agent Type -->
            <div class="grid grid-cols-12 gap-3">
              <div class="col-span-7">
                <label class="block text-[11px] text-[#909095] font-medium mb-1">Descrição Curta</label>
                <input
                  v-model="editForm.description"
                  type="text"
                  class="bento-input w-full py-1.5 px-3"
                  placeholder="Quando e como utilizar este agente..."
                />
              </div>
              <div class="col-span-5">
                <label class="block text-[11px] text-[#909095] font-medium mb-1">Tipo de Execução</label>
                <select v-model="editForm.agent_type" class="bento-input w-full py-1.5 px-3 bg-[#13151A]">
                  <option value="no-check">⚡ No-Check (Direto no editor)</option>
                  <option value="multi-check">🛡️ Multi-Check (Aprovação prévia)</option>
                </select>
              </div>
            </div>

            <!-- Row 2: Tone, Audience, Output Format -->
            <div class="grid grid-cols-3 gap-3">
              <div>
                <label class="block text-[11px] text-[#909095] font-medium mb-1">Tom de Comunicação</label>
                <input
                  v-model="editForm.tone"
                  type="text"
                  class="bento-input w-full py-1.5 px-3"
                  placeholder="Ex: humano e direto"
                />
              </div>
              <div>
                <label class="block text-[11px] text-[#909095] font-medium mb-1">Público-Alvo</label>
                <input
                  v-model="editForm.target_audience"
                  type="text"
                  class="bento-input w-full py-1.5 px-3"
                  placeholder="Ex: liderança, clientes"
                />
              </div>
              <div>
                <label class="block text-[11px] text-[#909095] font-medium mb-1">Formato de Saída</label>
                <select v-model="editForm.output_format" class="bento-input w-full py-1.5 px-3 bg-[#13151A]">
                  <option value="markdown">Markdown</option>
                  <option value="plain_text">Texto Puro (WhatsApp/Slack)</option>
                  <option value="email_blocks">Blocos de E-mail</option>
                  <option value="action_items">Ata & Tópicos de Ação</option>
                </select>
              </div>
            </div>

            <!-- Speech Cleanup Checkboxes -->
            <div class="flex items-center gap-6 p-2.5 rounded bg-[#13151A] border border-[#2D3342]">
              <label class="flex items-center gap-2 cursor-pointer">
                <input
                  v-model="editForm.remove_filler_words"
                  type="checkbox"
                  class="rounded border-[#2D3342] text-[#3B82F6] focus:ring-0"
                />
                <span class="text-[11px] text-[#DDE2F6]">Remover vícios de fala ("ehhh", "tipo assim", repetições)</span>
              </label>

              <label class="flex items-center gap-2 cursor-pointer">
                <input
                  v-model="editForm.preserve_slang"
                  type="checkbox"
                  class="rounded border-[#2D3342] text-[#3B82F6] focus:ring-0"
                />
                <span class="text-[11px] text-[#DDE2F6]">Preservar gírias e regionalismos</span>
              </label>
            </div>

            <!-- System Prompt (Master instructions) -->
            <div>
              <label class="block text-[11px] text-[#909095] font-medium mb-1">Instrução Mestre (System Prompt)</label>
              <textarea
                v-model="editForm.system_prompt"
                rows="5"
                class="bento-input w-full p-3 font-mono text-[11px] leading-relaxed resize-none"
                placeholder="Instruções de reescrita da IA..."
              ></textarea>
            </div>

            <!-- Row 3: Prefix Template & Suffix Template -->
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="block text-[11px] text-[#909095] font-medium mb-1">Prefixo / Saudação Inicial Fixa</label>
                <textarea
                  v-model="editForm.prefix_template"
                  rows="2"
                  class="bento-input w-full p-2 font-mono text-[11px] resize-none"
                  placeholder="Ex: Prezados(as),\n\n"
                ></textarea>
              </div>
              <div>
                <label class="block text-[11px] text-[#909095] font-medium mb-1">Sufixo / Assinatura Fixa</label>
                <textarea
                  v-model="editForm.suffix_template"
                  rows="2"
                  class="bento-input w-full p-2 font-mono text-[11px] resize-none"
                  placeholder="Ex: \n\nAtenciosamente,\n[Seu Nome]"
                ></textarea>
              </div>
            </div>
          </div>

          <!-- Footer Actions -->
          <div class="flex items-center justify-end gap-2 border-t border-[#2D3342] pt-3 flex-shrink-0">
            <button
              @click="editModalOpen = false"
              class="bento-btn px-3 py-1.5 text-xs text-[#909095] hover:text-[#DDE2F6]"
            >
              Cancelar
            </button>
            <button
              @click="handleSaveForm"
              class="bento-btn-primary px-4 py-1.5 text-xs font-semibold"
            >
              Salvar Agente
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue';
import { useRewriteAgents, type RewriteAgent } from '../../composables/useRewriteAgents';
import MetaAgentChatModal from './MetaAgentChatModal.vue';

const {
  agents,
  loading,
  error,
  fetchAgents,
  setDefaultAgent,
  deleteAgent,
  saveAgent,
} = useRewriteAgents();

// AI Creation / Edit Modal State
const aiModalOpen = ref(false);
const editingAIAgent = ref<RewriteAgent | null>(null);

// Edit Modal State
const editModalOpen = ref(false);
const editForm = reactive<Partial<RewriteAgent>>({
  name: '',
  slug: '',
  icon: '✨',
  description: '',
  system_prompt: '',
  tone: 'humano e direto',
  target_audience: 'geral',
  remove_filler_words: true,
  preserve_slang: false,
  prefix_template: '',
  suffix_template: '',
  output_format: 'markdown',
  provider: 'minimax',
  model: 'MiniMax-M2.7-highspeed',
  temperature: 0.3,
  is_default: false,
  agent_type: 'no-check',
});

function openAIModal() {
  editingAIAgent.value = null;
  aiModalOpen.value = true;
}

function openAIEdit(agent: RewriteAgent) {
  editingAIAgent.value = agent;
  aiModalOpen.value = true;
}

function handleCloseAIModal() {
  aiModalOpen.value = false;
  editingAIAgent.value = null;
}

function openManualCreate() {
  Object.assign(editForm, {
    id: undefined,
    name: '',
    slug: '',
    icon: '✨',
    description: '',
    system_prompt: '',
    tone: 'humano e direto',
    target_audience: 'geral',
    remove_filler_words: true,
    preserve_slang: false,
    prefix_template: '',
    suffix_template: '',
    output_format: 'markdown',
    provider: 'minimax',
    model: 'MiniMax-M2.7-highspeed',
    temperature: 0.3,
    is_default: false,
    agent_type: 'no-check',
  });
  editModalOpen.value = true;
}

function openEditModal(agent: RewriteAgent) {
  Object.assign(editForm, {
    ...agent,
    remove_filler_words: Boolean(agent.remove_filler_words),
    preserve_slang: Boolean(agent.preserve_slang),
    is_default: Boolean(agent.is_default),
    agent_type: agent.agent_type || 'no-check',
  });
  editModalOpen.value = true;
}

function handleEditFromAI(spec: Partial<RewriteAgent>) {
  Object.assign(editForm, {
    id: undefined,
    ...spec,
    remove_filler_words: Boolean(spec.remove_filler_words ?? true),
    preserve_slang: Boolean(spec.preserve_slang ?? false),
    is_default: false,
    agent_type: spec.agent_type || 'no-check',
  });
  editModalOpen.value = true;
}

async function handleSaveForm() {
  if (!editForm.name?.trim()) return;
  if (!editForm.slug?.trim()) {
    editForm.slug = editForm.name
      .toLowerCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '');
  }

  try {
    await saveAgent(editForm);
    editModalOpen.value = false;
  } catch (err) {
    console.error('Falha ao salvar agente:', err);
  }
}

async function handleDelete(id: number) {
  if (confirm('Deseja realmente excluir este agente de reescrita?')) {
    await deleteAgent(id);
  }
}

onMounted(() => {
  fetchAgents();
});
</script>
