<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-md p-4 select-none font-inter"
      @click.self="handleClose"
    >
      <div
        class="bg-[#16181F] border border-[#2D3342] rounded-2xl w-full max-w-3xl h-[86vh] shadow-2xl animate-slide-in flex flex-col overflow-hidden"
      >
        <!-- Modal Top Header -->
        <header class="flex items-center justify-between px-5 py-3.5 border-b border-[#2D3342] bg-[#1A1D24]/80 backdrop-blur flex-shrink-0">
          <div class="flex items-center gap-3">
            <div class="w-8 h-8 rounded-xl bg-[#10B981]/15 border border-[#10B981]/30 flex items-center justify-center text-[#10B981] shadow-sm">
              <span v-if="editingAgent?.icon" class="text-base">{{ editingAgent.icon }}</span>
              <svg v-else class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <div>
              <div class="flex items-center gap-2">
                <h3 class="text-xs font-bold text-[#DDE2F6]">
                  {{ editingAgent ? `Aperfeiçoar com IA: ${editingAgent.name}` : 'Arquiteto de Agentes IA' }}
                </h3>
                <span class="px-1.5 py-0.2 rounded text-[9.5px] font-mono bg-[#10B981]/20 text-[#34D399] border border-[#10B981]/30 font-semibold">
                  Agno + MiniMax
                </span>
              </div>
              <p class="text-[10.5px] text-[#909095]">
                {{ editingAgent ? 'Ajuste iterativo de diretrizes, regras e prompt mestre' : 'Entrevista consultiva para criação de agentes personalizados' }}
              </p>
            </div>
          </div>

          <div class="flex items-center gap-2">
            <button
              type="button"
              @click="handleRestart"
              :disabled="sending"
              class="px-2.5 py-1 rounded-lg text-xs bg-[#222733] text-[#909095] hover:text-[#DDE2F6] border border-[#3F444E] hover:border-[#3B82F6] transition-colors flex items-center gap-1.5"
              title="Limpar memória e reiniciar entrevista do zero"
            >
              <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              <span>Reiniciar</span>
            </button>
            <button
              type="button"
              @click="handleClose"
              class="text-[#909095] hover:text-[#DDE2F6] p-1.5 rounded-lg hover:bg-[#222733] transition-colors"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </header>

        <!-- Message Timeline -->
        <main
          ref="messagesContainer"
          class="flex-1 p-5 overflow-y-auto flex flex-col gap-4 bg-[#13151A] select-text"
        >
          <div
            v-for="(msg, index) in messages"
            :key="index"
            :class="[
              'flex gap-3 max-w-[88%]',
              msg.sender === 'user' ? 'self-end flex-row-reverse' : 'self-start'
            ]"
          >
            <!-- Avatar -->
            <div
              :class="[
                'w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 text-xs shadow-sm mt-0.5',
                msg.sender === 'user'
                  ? 'bg-[#3B82F6] text-white font-bold'
                  : 'bg-[#222733] border border-[#3F444E] text-[#10B981]'
              ]"
            >
              <span v-if="msg.sender === 'user'">👤</span>
              <span v-else>🤖</span>
            </div>

            <!-- Bubble Content -->
            <div
              :class="[
                'p-3.5 rounded-2xl text-xs leading-relaxed transition-all shadow-sm font-inter',
                msg.sender === 'user'
                  ? 'bg-[#2563EB] text-white rounded-tr-none'
                  : 'bg-[#1A1D24] text-[#DDE2F6] border border-[#2D3342] rounded-tl-none'
              ]"
            >
              <div
                v-if="msg.sender === 'architect'"
                class="chat-markdown-content leading-relaxed select-text"
                v-html="parseMarkdown(msg.text)"
              ></div>
              <div v-else class="whitespace-pre-wrap select-text">{{ msg.text }}</div>
              <div
                :class="[
                  'text-[9px] mt-1.5 text-right font-mono',
                  msg.sender === 'user' ? 'text-white/60' : 'text-[#909095]'
                ]"
              >
                {{ msg.time }}
              </div>
            </div>
          </div>

          <!-- Typing / Thinking State with Visual Reasoning Pulse -->
          <div v-if="sending" class="flex gap-3 max-w-[85%] self-start animate-fade-in">
            <div class="w-7 h-7 rounded-lg bg-[#222733] border border-[#10B981]/40 flex items-center justify-center flex-shrink-0 text-xs text-[#10B981] shadow-sm">
              <span class="animate-pulse">🧠</span>
            </div>
            <div class="p-3 bg-[#1A1D24] text-[#DDE2F6] border border-[#10B981]/30 rounded-2xl rounded-tl-none text-xs flex flex-col gap-1.5 shadow-lg backdrop-blur">
              <div class="flex items-center gap-2 text-[#34D399] font-medium text-[11px]">
                <svg class="animate-spin h-3.5 w-3.5 text-[#10B981]" viewBox="0 0 24 24" fill="none">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                </svg>
                <span>Arquiteto Agno: Raciocinando e estruturando diretrizes...</span>
              </div>
              <div class="flex items-center gap-1.5 text-[9.5px] font-mono text-[#909095]">
                <span class="px-1.5 py-0.5 rounded bg-[#13151A] border border-[#2D3342] text-[#60A5FA]">1. Análise de Cenário</span>
                <span>➔</span>
                <span class="px-1.5 py-0.5 rounded bg-[#13151A] border border-[#2D3342] text-[#34D399]">2. Calibração Multi-Check</span>
                <span>➔</span>
                <span class="px-1.5 py-0.5 rounded bg-[#13151A] border border-[#2D3342] text-[#F59E0B]">3. Engenharia de Prompt</span>
              </div>
            </div>
          </div>

          <!-- Generated Agent Specification Card -->
          <div
            v-if="generatedSpec"
            class="bento-card p-4 border-[#10B981]/50 bg-[#16181F]/90 shadow-2xl flex flex-col gap-3 my-2 animate-slide-in"
          >
            <div class="flex items-center justify-between border-b border-[#2D3342] pb-2.5">
              <div class="flex items-center gap-2">
                <span class="text-2xl p-1.5 rounded-lg bg-[#222733] border border-[#3F444E]">{{ generatedSpec.icon || '✨' }}</span>
                <div>
                  <div class="flex items-center gap-2">
                    <span class="text-xs font-bold text-[#DDE2F6]">{{ generatedSpec.name }}</span>
                    <span class="px-1.5 py-0.2 rounded text-[9px] font-mono bg-[#10B981]/20 text-[#34D399] border border-[#10B981]/30">
                      Especificação Pronta
                    </span>
                    <span
                      :class="[
                        'px-1.5 py-0.2 rounded text-[9px] font-mono border font-semibold',
                        generatedSpec.agent_type === 'multi-check'
                          ? 'bg-[#10B981]/20 text-[#34D399] border-[#10B981]/30'
                          : 'bg-[#3B82F6]/20 text-[#60A5FA] border-[#3B82F6]/30'
                      ]"
                    >
                      {{ generatedSpec.agent_type === 'multi-check' ? '🛡️ Multi-Check' : '⚡ No-Check' }}
                    </span>
                  </div>
                  <p class="text-[10.5px] text-[#909095]">{{ generatedSpec.description }}</p>
                </div>
              </div>
            </div>

            <!-- Parameters Grid -->
            <div class="grid grid-cols-2 md:grid-cols-5 gap-2 text-[10px] font-mono">
              <div class="p-2 rounded bg-[#13151A] border border-[#2D3342]">
                <span class="text-[#909095] block">Modo:</span>
                <span :class="generatedSpec.agent_type === 'multi-check' ? 'text-[#10B981]' : 'text-[#60A5FA]'" class="font-semibold">
                  {{ generatedSpec.agent_type === 'multi-check' ? 'Multi-Check' : 'No-Check' }}
                </span>
              </div>
              <div class="p-2 rounded bg-[#13151A] border border-[#2D3342]">
                <span class="text-[#909095] block">Tom:</span>
                <span class="text-[#DDE2F6] font-semibold">{{ generatedSpec.tone }}</span>
              </div>
              <div class="p-2 rounded bg-[#13151A] border border-[#2D3342]">
                <span class="text-[#909095] block">Público:</span>
                <span class="text-[#DDE2F6] font-semibold">{{ generatedSpec.target_audience }}</span>
              </div>
              <div class="p-2 rounded bg-[#13151A] border border-[#2D3342]">
                <span class="text-[#909095] block">Formato:</span>
                <span class="text-[#DDE2F6] font-semibold">{{ generatedSpec.output_format }}</span>
              </div>
              <div class="p-2 rounded bg-[#13151A] border border-[#2D3342]">
                <span class="text-[#909095] block">Limpeza de Fala:</span>
                <span class="text-[#10B981] font-semibold">
                  {{ generatedSpec.remove_filler_words ? '✓ Sem vícios' : 'Original' }}
                </span>
              </div>
            </div>

            <!-- System Prompt Accordion/Preview -->
            <div>
              <button
                type="button"
                @click="showPromptPreview = !showPromptPreview"
                class="text-[10.5px] text-[#3B82F6] hover:underline flex items-center gap-1 font-medium"
              >
                <span>{{ showPromptPreview ? '▾ Ocultar System Prompt Gerado' : '▸ Ver System Prompt Gerado pelo Arquiteto' }}</span>
              </button>
              <div
                v-if="showPromptPreview"
                class="mt-2 p-3 rounded-lg bg-[#13151A] border border-[#2D3342] max-h-36 overflow-y-auto text-[11px] font-mono text-[#DDE2F6] leading-relaxed select-text whitespace-pre-wrap"
              >
                {{ generatedSpec.system_prompt }}
              </div>
            </div>

            <!-- Card Actions -->
            <div class="flex items-center justify-end gap-2 pt-2 border-t border-[#2D3342]">
              <button
                type="button"
                @click="handleEditInForm"
                class="bento-btn px-3 py-1.5 text-xs text-[#DDE2F6]"
              >
                Ajustar no Editor
              </button>
              <button
                type="button"
                @click="handleSaveAgent"
                class="bento-btn-primary px-4 py-1.5 text-xs font-semibold bg-[#10B981] hover:bg-[#059669] text-white border-none flex items-center gap-1.5"
              >
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7" />
                </svg>
                <span>Aprovar &amp; Salvar Agente</span>
              </button>
            </div>
          </div>
        </main>

        <!-- Quick Suggestions & Rich Textarea Input Footer -->
        <footer class="p-4 border-t border-[#2D3342] bg-[#16181F] flex flex-col gap-2.5 flex-shrink-0">
          <!-- Suggestion Chips -->
          <div class="flex flex-wrap items-center gap-1.5">
            <span class="text-[10px] text-[#909095] font-mono mr-1">Sugestões:</span>
            <button
              v-for="(sug, idx) in suggestions"
              :key="idx"
              type="button"
              @click="applySuggestion(sug)"
              :disabled="sending"
              class="px-2 py-0.5 rounded-full text-[10.5px] bg-[#222733] hover:bg-[#3B82F6]/20 text-[#909095] hover:text-[#60A5FA] border border-[#3F444E] hover:border-[#3B82F6]/50 transition-colors"
            >
              {{ sug }}
            </button>
          </div>

          <!-- Multiline Textarea Box with Bento Styling -->
          <div class="flex flex-col gap-2 bg-[#13151A] border border-[#2D3342] rounded-xl p-3 focus-within:border-[#10B981] focus-within:ring-1 focus-within:ring-[#10B981]/40 transition-all shadow-inner">
            <textarea
              ref="textareaRef"
              v-model="userInput"
              rows="3"
              placeholder="Descreva detalhadamente o que você precisa ou responda ao Arquiteto..."
              :disabled="sending"
              @keydown="handleKeyDown"
              class="w-full bg-transparent text-xs text-[#DDE2F6] placeholder-[#909095]/60 focus:outline-none resize-none leading-relaxed min-h-[64px] max-h-[160px] select-text font-inter"
            ></textarea>

            <div class="flex items-center justify-between pt-2 border-t border-[#2D3342]/60 text-[10px] text-[#909095] font-mono">
              <div class="flex items-center gap-2">
                <span>💡 <strong>Enter</strong> para enviar, <strong>Shift + Enter</strong> para nova linha</span>
              </div>
              <div class="flex items-center gap-2">
                <button
                  type="button"
                  v-if="userInput.trim()"
                  @click="userInput = ''"
                  class="px-2 py-1 text-[#909095] hover:text-[#EF4444] text-[10px] transition-colors"
                >
                  Limpar
                </button>
                <button
                  type="button"
                  @click="handleSendMessage"
                  :disabled="sending || !userInput.trim()"
                  class="bento-btn-primary px-4 py-1.5 text-xs font-semibold bg-[#10B981] hover:bg-[#059669] text-white border-none flex items-center gap-1.5 disabled:opacity-40 shadow-sm cursor-pointer"
                >
                  <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                  </svg>
                  <span>Enviar Mensagem</span>
                </button>
              </div>
            </div>
          </div>
        </footer>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, reactive, watch, nextTick } from 'vue';
import { useRewriteAgents, type RewriteAgent } from '../../composables/useRewriteAgents';

const props = defineProps<{
  visible: boolean;
  editingAgent?: Partial<RewriteAgent> | null;
}>();

const emit = defineEmits<{
  'close': [];
  'agent-saved': [];
  'edit-agent': [agent: Partial<RewriteAgent>];
}>();

const { startBuilderSession, sendBuilderMessage, resetBuilderSession, saveAgent } = useRewriteAgents();

interface ChatMessage {
  sender: 'architect' | 'user';
  text: string;
  time: string;
}

const currentSessionId = ref<string>('');
const messages = reactive<ChatMessage[]>([]);
const userInput = ref('');
const sending = ref(false);
const generatedSpec = ref<Partial<RewriteAgent> | null>(null);
const showPromptPreview = ref(false);

const messagesContainer = ref<HTMLElement | null>(null);
const textareaRef = ref<HTMLTextAreaElement | null>(null);

const suggestions = ref<string[]>([
  'Mensagens rápidas no WhatsApp/Slack',
  'E-mail formal com assinatura',
  'Ata executiva de reunião',
  'Pode finalizar e gerar o agente',
]);

function formatCurrentTime() {
  const now = new Date();
  return now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function parseMarkdown(text: string): string {
  if (!text) return '';
  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // Code blocks
  html = html.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, (_match, _lang, code) => {
    return `<pre class="my-2 p-2.5 rounded-lg bg-[#0F1115] border border-[#2D3342] text-[11px] font-mono text-[#DDE2F6] overflow-x-auto select-text"><code>${code.trim()}</code></pre>`;
  });

  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code class="px-1.5 py-0.5 rounded bg-[#13151A] border border-[#2D3342] text-[#F59E0B] font-mono text-[10.5px] select-text">$1</code>');

  // Headers
  html = html.replace(/^### (.*$)/gim, '<h3 class="text-xs font-bold text-[#DDE2F6] mt-2.5 mb-1">$1</h3>');
  html = html.replace(/^## (.*$)/gim, '<h2 class="text-sm font-bold text-[#DDE2F6] mt-3 mb-1.5">$1</h2>');
  html = html.replace(/^# (.*$)/gim, '<h1 class="text-base font-bold text-[#DDE2F6] mt-3 mb-2">$1</h1>');

  // Bold & Italic
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong class="font-bold text-white">$1</strong>');
  html = html.replace(/\*([^*]+)\*/g, '<em class="italic text-[#E5E7EB]">$1</em>');

  // Blockquotes
  html = html.replace(/^> (.*$)/gim, '<blockquote class="border-l-2 border-[#10B981] pl-2.5 py-0.5 my-1.5 text-[#909095] italic">$1</blockquote>');

  // Lists
  html = html.replace(/^\s*[-*]\s+(.*$)/gim, '<li class="ml-4 list-disc text-[#DDE2F6] my-0.5">$1</li>');
  html = html.replace(/^\s*(\d+)\.\s+(.*$)/gim, '<li class="ml-4 list-decimal text-[#DDE2F6] my-0.5">$2</li>');

  // Line breaks
  html = html.replace(/\n\n/g, '<div class="h-2"></div>');
  html = html.replace(/\n/g, '<br/>');

  return html;
}

async function scrollToBottom(force = false) {
  await nextTick();
  if (messagesContainer.value) {
    messagesContainer.value.scrollTo({
      top: messagesContainer.value.scrollHeight,
      behavior: force ? 'auto' : 'smooth',
    });
  }
}

function handleKeyDown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    handleSendMessage();
  }
}

async function initSession() {
  messages.length = 0;
  generatedSpec.value = null;
  showPromptPreview.value = false;
  userInput.value = '';

  try {
    sending.value = true;
    const res = await startBuilderSession(undefined, props.editingAgent || undefined);
    currentSessionId.value = res.session_id;
    messages.push({
      sender: 'architect',
      text: res.message,
      time: formatCurrentTime(),
    });
  } catch (err) {
    console.error('Erro ao iniciar sessão do Arquiteto:', err);
  } finally {
    sending.value = false;
    await scrollToBottom();
    nextTick(() => textareaRef.value?.focus());
  }
}

async function handleSendMessage() {
  const text = userInput.value.trim();
  if (!text || sending.value) return;

  userInput.value = '';
  messages.push({
    sender: 'user',
    text: text,
    time: formatCurrentTime(),
  });
  await scrollToBottom();

  sending.value = true;
  try {
    const res = await sendBuilderMessage(currentSessionId.value, text);
    messages.push({
      sender: 'architect',
      text: res.reply,
      time: formatCurrentTime(),
    });

    if (res.is_complete && res.agent_spec) {
      generatedSpec.value = res.agent_spec;
    }
  } catch (err: any) {
    messages.push({
      sender: 'architect',
      text: `⚠️ Desculpe, ocorreu um erro na comunicação: ${err.message || err}`,
      time: formatCurrentTime(),
    });
  } finally {
    sending.value = false;
    await scrollToBottom();
    nextTick(() => textareaRef.value?.focus());
  }
}

function applySuggestion(sug: string) {
  userInput.value = sug;
  handleSendMessage();
}

async function handleRestart() {
  if (currentSessionId.value) {
    await resetBuilderSession(currentSessionId.value);
  }
  await initSession();
}

async function handleClose() {
  if (currentSessionId.value) {
    await resetBuilderSession(currentSessionId.value);
    currentSessionId.value = '';
  }
  emit('close');
}

async function handleSaveAgent() {
  if (!generatedSpec.value) return;
  try {
    const payloadToSave: Partial<RewriteAgent> = {
      ...generatedSpec.value,
      ...(props.editingAgent?.id ? { id: props.editingAgent.id } : {}),
      ...(props.editingAgent?.slug ? { slug: props.editingAgent.slug } : {}),
    };
    await saveAgent(payloadToSave);
    await handleClose();
    emit('agent-saved');
  } catch (err) {
    console.error('Erro ao salvar agente:', err);
  }
}

function handleEditInForm() {
  if (!generatedSpec.value) return;
  const specCopy = {
    ...generatedSpec.value,
    ...(props.editingAgent?.id ? { id: props.editingAgent.id } : {}),
    ...(props.editingAgent?.slug ? { slug: props.editingAgent.slug } : {}),
  };
  handleClose();
  emit('edit-agent', specCopy);
}

watch(
  () => [messages.length, sending.value, generatedSpec.value],
  () => {
    scrollToBottom();
  },
  { deep: true }
);

watch(
  () => props.visible,
  (isVis) => {
    if (isVis) {
      initSession();
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

@keyframes fade-in {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.animate-slide-in {
  animation: slide-in 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

.animate-fade-in {
  animation: fade-in 0.15s ease-out;
}
</style>
