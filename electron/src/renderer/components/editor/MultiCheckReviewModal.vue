<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 select-none font-inter"
      @click.self="handleReject"
    >
      <div
        class="bg-[#16181F] border border-[#2D3342] rounded-2xl w-full max-w-4xl h-[90vh] shadow-2xl animate-slide-in flex flex-col overflow-hidden"
      >
        <!-- Modal Top Header -->
        <header class="flex items-center justify-between px-6 py-3.5 border-b border-[#2D3342] bg-[#1A1D24]/90 backdrop-blur flex-shrink-0">
          <div class="flex items-center gap-3">
            <div class="w-9 h-9 rounded-xl bg-[#3B82F6]/15 border border-[#3B82F6]/30 flex items-center justify-center text-lg shadow-sm">
              {{ agent?.icon || '✨' }}
            </div>
            <div>
              <div class="flex items-center gap-2">
                <h3 class="text-xs font-bold text-[#DDE2F6]">{{ agent?.name || 'Reestruturador' }}</h3>
                <span class="px-1.5 py-0.2 rounded text-[9.5px] font-mono bg-[#3B82F6]/20 text-[#60A5FA] border border-[#3B82F6]/30 font-semibold">
                  🛡️ Multi-Check (Aprovação Prévia)
                </span>
                <span class="px-1.5 py-0.2 rounded text-[9px] font-mono bg-[#222733] text-[#909095] border border-[#3F444E]">
                  Revisão {{ revisionCount }}
                </span>
              </div>
              <p class="text-[10.5px] text-[#909095]">Revise, solicite ajustes iterativos ou aprove para substituir no editor</p>
            </div>
          </div>

          <div class="flex items-center gap-2">
            <button
              type="button"
              @click="handleReject"
              class="px-2.5 py-1.5 rounded-lg text-xs bg-[#222733] hover:bg-[#EF4444]/20 text-[#909095] hover:text-[#EF4444] border border-[#3F444E] hover:border-[#EF4444]/40 transition-colors flex items-center gap-1"
              title="Cancelar e manter o texto original intacto"
            >
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
              <span>Descartar</span>
            </button>
          </div>
        </header>

        <!-- Main Body (Scrollable Draft View & Original Accordion) -->
        <main class="flex-1 p-6 overflow-y-auto flex flex-col gap-4 bg-[#13151A] select-text">
          <!-- Status Banner during Generation -->
          <div
            v-if="rewriting"
            class="p-3 rounded-xl bg-[#1A1D24] border border-[#3B82F6]/40 text-xs flex items-center justify-between animate-pulse flex-shrink-0"
          >
            <div class="flex items-center gap-2 text-[#60A5FA]">
              <svg class="animate-spin h-4 w-4 text-[#60A5FA]" viewBox="0 0 24 24" fill="none">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
              </svg>
              <span class="font-medium">{{ reasoningStage || 'Processando raciocínio e sintetizando texto...' }}</span>
            </div>
            <span class="text-[10px] font-mono text-[#909095]">Stream SSE Ativo</span>
          </div>

          <!-- Reasoning Trace Box (if emitted by AI) -->
          <div
            v-if="reasoningText"
            class="p-3.5 rounded-xl bg-[#16181F] border border-[#3B82F6]/30 text-xs flex flex-col gap-1.5 shadow-inner"
          >
            <button
              type="button"
              @click="showReasoning = !showReasoning"
              class="flex items-center justify-between text-[#60A5FA] font-medium text-[11px] hover:underline"
            >
              <div class="flex items-center gap-1.5">
                <span class="inline-block w-1.5 h-1.5 rounded-full bg-[#60A5FA] animate-ping"></span>
                <span>🧠 Raciocínio Analítico da IA (Reasoning)</span>
              </div>
              <span class="text-[10px] text-[#909095]">{{ showReasoning ? '▲ Ocultar' : '▼ Expandir' }}</span>
            </button>
            <div
              v-if="showReasoning"
              class="p-2.5 rounded-lg bg-[#13151A] text-[11px] font-mono text-[#DDE2F6] leading-relaxed max-h-36 overflow-y-auto whitespace-pre-wrap mt-1"
            >
              {{ reasoningText }}
            </div>
          </div>

          <!-- Current Restructured Text Draft Card -->
          <div class="bento-card p-5 bg-[#16181F] border-[#3B82F6]/50 shadow-2xl flex flex-col gap-3 flex-1">
            <div class="flex items-center justify-between border-b border-[#2D3342] pb-2.5">
              <div class="flex items-center gap-2">
                <span class="w-2 h-2 rounded-full bg-[#10B981]"></span>
                <h4 class="text-xs font-bold text-[#DDE2F6]">Texto Reestruturado (Rascunho Atual)</h4>
              </div>
              <div class="flex items-center gap-2 text-[10px] font-mono text-[#909095]">
                <span>{{ draftText.split(/\s+/).filter(Boolean).length }} palavras</span>
                <span>•</span>
                <span>{{ draftText.length }} caracteres</span>
              </div>
            </div>

            <!-- Draft Content (Markdown Rendered or Plain text) -->
            <div
              class="flex-1 min-h-[160px] p-4 rounded-xl bg-[#13151A] border border-[#2D3342] text-xs text-[#DDE2F6] leading-relaxed overflow-y-auto font-inter select-text whitespace-pre-wrap"
            >
              {{ draftText }}
            </div>
          </div>

          <!-- Collapsible Original Text Reference -->
          <div class="rounded-xl border border-[#2D3342] bg-[#16181F] p-3 text-xs flex flex-col gap-2">
            <button
              type="button"
              @click="showOriginal = !showOriginal"
              class="flex items-center justify-between text-[#909095] hover:text-[#DDE2F6] font-medium"
            >
              <div class="flex items-center gap-1.5">
                <span>📄 Ver Texto Original da Transcrição</span>
                <span class="text-[10px] text-[#909095]">({{ originalText.length }} caracteres)</span>
              </div>
              <span class="text-[10px]">{{ showOriginal ? '▲ Recolher' : '▼ Expandir' }}</span>
            </button>
            <div
              v-if="showOriginal"
              class="p-3 rounded-lg bg-[#13151A] border border-[#2D3342] text-[11px] text-[#909095] max-h-36 overflow-y-auto leading-relaxed select-text whitespace-pre-wrap font-mono"
            >
              {{ originalText }}
            </div>
          </div>
        </main>

        <!-- Iterative Feedback Dock & Actions Footer -->
        <footer class="p-5 border-t border-[#2D3342] bg-[#16181F] flex flex-col gap-3 flex-shrink-0">
          <!-- Suggestion Chips for Feedback -->
          <div class="flex flex-wrap items-center gap-1.5">
            <span class="text-[10px] text-[#909095] font-mono mr-1">Sugestões de Ajuste:</span>
            <button
              v-for="(sug, idx) in feedbackSuggestions"
              :key="idx"
              type="button"
              @click="applyFeedbackSuggestion(sug)"
              :disabled="rewriting"
              class="px-2 py-0.5 rounded-full text-[10.5px] bg-[#222733] hover:bg-[#3B82F6]/20 text-[#909095] hover:text-[#60A5FA] border border-[#3F444E] hover:border-[#3B82F6]/50 transition-colors"
            >
              {{ sug }}
            </button>
          </div>

          <!-- Feedback Input Row -->
          <div class="flex items-start gap-2 bg-[#13151A] border border-[#2D3342] rounded-xl p-2.5 focus-within:border-[#3B82F6] focus-within:ring-1 focus-within:ring-[#3B82F6]/40 transition-all shadow-inner">
            <textarea
              v-model="feedbackInput"
              rows="2"
              placeholder="Não gostou de algo ou deseja mudar um trecho? Digite seu feedback para a IA ajustar o texto..."
              :disabled="rewriting"
              @keydown.enter.exact.prevent="handleSendFeedback"
              class="w-full bg-transparent text-xs text-[#DDE2F6] placeholder-[#909095]/60 focus:outline-none resize-none leading-relaxed min-h-[44px] select-text font-inter"
            ></textarea>
            <button
              type="button"
              @click="handleSendFeedback"
              :disabled="rewriting || !feedbackInput.trim()"
              class="bento-btn px-3 py-2 text-xs font-semibold text-[#3B82F6] hover:text-white hover:bg-[#3B82F6] border-[#3B82F6]/50 transition-all flex items-center gap-1.5 flex-shrink-0 disabled:opacity-30 mt-0.5 cursor-pointer"
              title="Refinar rascunho com o feedback digitado"
            >
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              <span>Ajustar Rascunho</span>
            </button>
          </div>

          <!-- Bottom Action Buttons -->
          <div class="flex items-center justify-between pt-2 border-t border-[#2D3342]/60">
            <button
              type="button"
              @click="handleReject"
              :disabled="rewriting"
              class="bento-btn px-4 py-2 text-xs text-[#909095] hover:text-[#EF4444] hover:border-[#EF4444]/40"
            >
              ❌ Rejeitar &amp; Manter Original
            </button>

            <div class="flex items-center gap-2">
              <button
                type="button"
                @click="handleApprove"
                :disabled="rewriting || !draftText.trim()"
                class="bento-btn-primary px-6 py-2 text-xs font-bold bg-gradient-to-r from-[#10B981] to-[#059669] hover:from-[#059669] hover:to-[#047857] text-white border-none flex items-center gap-2 shadow-lg disabled:opacity-40 cursor-pointer"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7" />
                </svg>
                <span>Aprovar &amp; Inserir no Editor</span>
              </button>
            </div>
          </div>
        </footer>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue';
import { useRewriteAgents, type RewriteAgent } from '../../composables/useRewriteAgents';

const props = defineProps<{
  visible: boolean;
  agent: RewriteAgent | null;
  originalText: string;
  initialDraft?: string;
}>();

const emit = defineEmits<{
  'approve': [finalText: string];
  'reject': [];
  'close': [];
}>();

const {
  rewriting,
  reasoningText,
  reasoningStage,
  executeRewriteStream,
  executeRewriteFeedbackStream,
} = useRewriteAgents();

const draftText = ref('');
const feedbackInput = ref('');
const revisionCount = ref(1);
const showOriginal = ref(false);
const showReasoning = ref(true);

const feedbackSuggestions = ref<string[]>([
  'Deixe mais conciso e direto',
  'Separe os tópicos em parágrafos distintos',
  'Ajuste o tom para ser mais formal',
  'Mantenha os termos técnicos originais',
]);

function applyFeedbackSuggestion(sug: string) {
  feedbackInput.value = sug;
  handleSendFeedback();
}

async function startInitialDraft() {
  if (!props.agent || !props.originalText) return;
  revisionCount.value = 1;
  draftText.value = '';
  feedbackInput.value = '';
  showOriginal.value = false;
  showReasoning.value = true;

  try {
    const result = await executeRewriteStream(props.originalText, (accumulated) => {
      draftText.value = accumulated;
    });
    if (result) {
      draftText.value = result;
    }
  } catch (err) {
    console.error('Erro na geração inicial do rascunho:', err);
  }
}

async function handleSendFeedback() {
  const fb = feedbackInput.value.trim();
  if (!fb || rewriting.value || !props.agent) return;

  feedbackInput.value = '';
  revisionCount.value++;
  showReasoning.value = true;

  try {
    const updated = await executeRewriteFeedbackStream(
      props.agent.id,
      props.originalText,
      draftText.value,
      fb,
      props.agent.model,
      (accumulated) => {
        draftText.value = accumulated;
      }
    );
    if (updated) {
      draftText.value = updated;
    }
  } catch (err) {
    console.error('Erro ao enviar feedback para o agente:', err);
  }
}

function handleApprove() {
  if (!draftText.value.trim()) return;
  emit('approve', draftText.value);
  emit('close');
}

function handleReject() {
  emit('reject');
  emit('close');
}

watch(
  () => props.visible,
  (isVis) => {
    if (isVis) {
      if (props.initialDraft) {
        draftText.value = props.initialDraft;
      } else {
        startInitialDraft();
      }
    }
  }
);
</script>

<style scoped>
@keyframes slide-in {
  from {
    opacity: 0;
    transform: translateY(12px) scale(0.98);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.animate-slide-in {
  animation: slide-in 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}
</style>
