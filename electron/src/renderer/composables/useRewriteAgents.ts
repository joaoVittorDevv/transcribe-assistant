import { ref, computed } from 'vue';

export interface RewriteAgent {
  id: number;
  name: string;
  slug: string;
  icon: string;
  description: string;
  system_prompt: string;
  tone: string;
  target_audience: string;
  remove_filler_words: boolean | number;
  preserve_slang: boolean | number;
  prefix_template: string;
  suffix_template: string;
  output_format: string;
  provider: string;
  model: string;
  temperature: number;
  is_default: boolean | number;
  agent_type: 'multi-check' | 'no-check';
  created_at?: string;
  updated_at?: string;
}

const agents = ref<RewriteAgent[]>([]);
const activeAgentId = ref<number | null>(null);
const loading = ref(false);
const rewriting = ref(false);
const error = ref<string | null>(null);

const API = 'http://localhost:18763';

const reasoningText = ref<string>('');
const reasoningStage = ref<string>('');
const isReasoningExpanded = ref<boolean>(false);

export function useRewriteAgents() {
  const activeAgent = computed(() => {
    return agents.value.find((a) => a.id === activeAgentId.value) || agents.value[0] || null;
  });

  async function fetchAgents(): Promise<void> {
    loading.value = true;
    error.value = null;
    try {
      const res = await fetch(`${API}/agents`);
      if (!res.ok) throw new Error(`Falha ao buscar agentes: ${res.statusText}`);
      const data = await res.json();
      agents.value = Array.isArray(data) ? data : (data.agents || []);

      if ((!activeAgentId.value || !agents.value.some((a) => a.id === activeAgentId.value)) && agents.value.length > 0) {
        const defaultAgent = agents.value.find((a) => Boolean(a.is_default)) || agents.value[0];
        activeAgentId.value = defaultAgent.id;
      }
    } catch (err: any) {
      console.error('Erro ao carregar agentes:', err);
      error.value = err.message;
    } finally {
      loading.value = false;
    }
  }

  function setActiveAgentId(id: number) {
    activeAgentId.value = id;
  }

  async function executeRewriteStream(
    text: string,
    onChunk?: (accumulated: string, delta: string) => void,
    onReasoning?: (accumulatedReasoning: string, deltaReasoning: string) => void
  ): Promise<string> {
    if (!activeAgent.value) {
      throw new Error('Nenhum agente selecionado para reescrita.');
    }
    if (!text || !text.trim()) {
      return text;
    }

    rewriting.value = true;
    error.value = null;
    reasoningText.value = '';
    reasoningStage.value = 'Analisando contexto e nuances da fala...';

    try {
      const res = await fetch(`${API}/agents/rewrite/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          agent_id: activeAgent.value.id,
          text: text,
          model: activeAgent.value.model,
        }),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Erro na reescrita em stream: ${res.statusText}`);
      }

      if (!res.body) {
        throw new Error('ReadableStream não suportado pelo backend.');
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let accumulatedContent = '';
      let accumulatedReasoning = '';
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith('data:')) continue;
          const jsonStr = trimmed.slice(5).trim();
          if (!jsonStr) continue;

          try {
            const parsed = JSON.parse(jsonStr);
            if (parsed.type === 'error' || parsed.error) {
              throw new Error(parsed.error || 'Erro no processamento da IA');
            }

            if (parsed.type === 'status') {
              reasoningStage.value = parsed.stage || '';
            } else if (parsed.type === 'reasoning') {
              accumulatedReasoning += parsed.chunk || '';
              reasoningText.value = accumulatedReasoning;
              if (onReasoning) {
                onReasoning(accumulatedReasoning, parsed.chunk || '');
              }
            } else if (parsed.type === 'content' || parsed.chunk) {
              const delta = parsed.chunk || '';
              accumulatedContent += delta;
              if (onChunk) {
                onChunk(accumulatedContent, delta);
              }
            }
          } catch (e: any) {
            if (e.message && !e.message.includes('JSON')) {
              console.warn('Erro ao processar evento SSE:', e);
            }
          }
        }
      }

      return accumulatedContent || text;
    } catch (err: any) {
      console.error('Erro ao executar reescrita em stream:', err);
      error.value = err.message || 'Falha ao reescrever texto.';
      throw err;
    } finally {
      rewriting.value = false;
    }
  }

  async function executeRewriteFeedbackStream(
    agentId: number,
    originalText: string,
    currentDraft: string,
    feedback: string,
    modelName?: string,
    onChunk?: (accumulated: string, delta: string) => void,
    onReasoning?: (accumulatedReasoning: string, deltaReasoning: string) => void
  ): Promise<string> {
    rewriting.value = true;
    error.value = null;
    reasoningText.value = '';
    reasoningStage.value = 'Analisando seu feedback e ajustando o texto...';

    try {
      const res = await fetch(`${API}/agents/rewrite/feedback/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          agent_id: agentId,
          original_text: originalText,
          current_draft: currentDraft,
          feedback: feedback,
          model: modelName,
        }),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Erro no feedback loop: ${res.statusText}`);
      }

      if (!res.body) {
        throw new Error('ReadableStream não suportado pelo backend.');
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let accumulatedContent = '';
      let accumulatedReasoning = '';
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith('data:')) continue;
          const jsonStr = trimmed.slice(5).trim();
          if (!jsonStr) continue;

          try {
            const parsed = JSON.parse(jsonStr);
            if (parsed.type === 'error' || parsed.error) {
              throw new Error(parsed.error || 'Erro no processamento da IA');
            }

            if (parsed.type === 'status') {
              reasoningStage.value = parsed.stage || '';
            } else if (parsed.type === 'reasoning') {
              accumulatedReasoning += parsed.chunk || '';
              reasoningText.value = accumulatedReasoning;
              if (onReasoning) {
                onReasoning(accumulatedReasoning, parsed.chunk || '');
              }
            } else if (parsed.type === 'content' || parsed.chunk) {
              const delta = parsed.chunk || '';
              accumulatedContent += delta;
              if (onChunk) {
                onChunk(accumulatedContent, delta);
              }
            }
          } catch (e: any) {
            if (e.message && !e.message.includes('JSON')) {
              console.warn('Erro ao processar evento SSE:', e);
            }
          }
        }
      }

      return accumulatedContent || currentDraft;
    } catch (err: any) {
      console.error('Erro ao refinar texto com feedback:', err);
      error.value = err.message || 'Falha ao ajustar texto.';
      throw err;
    } finally {
      rewriting.value = false;
    }
  }

  async function executeRewrite(text: string): Promise<string> {
    if (!activeAgent.value) {
      throw new Error('Nenhum agente selecionado para reescrita.');
    }
    if (!text || !text.trim()) {
      return text;
    }

    rewriting.value = true;
    error.value = null;

    try {
      const res = await fetch(`${API}/agents/rewrite`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          agent_id: activeAgent.value.id,
          text: text,
        }),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Erro na reescrita: ${res.statusText}`);
      }

      const data = await res.json();
      return data.rewritten_text || text;
    } catch (err: any) {
      console.error('Erro ao executar reescrita:', err);
      error.value = err.message || 'Falha ao reescrever texto.';
      throw err;
    } finally {
      rewriting.value = false;
    }
  }

  async function startBuilderSession(
    modelName?: string,
    initialAgent?: Partial<RewriteAgent>
  ): Promise<{ session_id: string; message: string }> {
    loading.value = true;
    error.value = null;
    try {
      const sessionId = 'builder-' + Math.random().toString(36).substring(2, 9);
      const res = await fetch(`${API}/agents/builder/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          model: modelName,
          initial_agent: initialAgent || null,
        }),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || 'Erro ao iniciar sessão com o Arquiteto Agno.');
      }

      const data = await res.json();
      return { session_id: data.session_id, message: data.message };
    } catch (err: any) {
      console.error('Erro ao iniciar Arquiteto:', err);
      error.value = err.message;
      throw err;
    } finally {
      loading.value = false;
    }
  }

  async function sendBuilderMessage(
    sessionId: string,
    message: string,
    modelName?: string
  ): Promise<{ reply: string; is_complete: boolean; agent_spec: Partial<RewriteAgent> | null }> {
    loading.value = true;
    error.value = null;
    try {
      const res = await fetch(`${API}/agents/builder/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          message: message,
          model: modelName,
        }),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || 'Erro ao conversar com o Arquiteto Agno.');
      }

      const data = await res.json();
      return {
        reply: data.reply,
        is_complete: Boolean(data.is_complete),
        agent_spec: data.agent_spec || null,
      };
    } catch (err: any) {
      console.error('Erro na mensagem do Arquiteto:', err);
      error.value = err.message;
      throw err;
    } finally {
      loading.value = false;
    }
  }

  async function resetBuilderSession(sessionId: string): Promise<void> {
    try {
      await fetch(`${API}/agents/builder/reset`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId }),
      });
    } catch (err) {
      console.warn('Erro ao resetar sessão do builder:', err);
    }
  }

  async function createAgentWithAI(userIntent: string): Promise<Partial<RewriteAgent>> {
    loading.value = true;
    error.value = null;
    try {
      const sess = await startBuilderSession();
      const chatRes = await sendBuilderMessage(sess.session_id, userIntent);
      await resetBuilderSession(sess.session_id);
      if (chatRes.agent_spec) {
        return chatRes.agent_spec;
      }
      throw new Error('O Arquiteto gerou uma resposta conversacional. Use o modo interativo.');
    } catch (err: any) {
      console.error('Erro no Meta-Agente:', err);
      error.value = err.message;
      throw err;
    } finally {
      loading.value = false;
    }
  }

  async function saveAgent(agent: Partial<RewriteAgent>): Promise<void> {
    loading.value = true;
    error.value = null;
    try {
      const isEdit = Boolean(agent.id);
      const url = isEdit ? `${API}/agents/${agent.id}` : `${API}/agents`;
      const method = isEdit ? 'PUT' : 'POST';

      const res = await fetch(url, {
        method: method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(agent),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || 'Erro ao salvar agente.');
      }

      await fetchAgents();
    } catch (err: any) {
      console.error('Erro ao salvar agente:', err);
      error.value = err.message;
      throw err;
    } finally {
      loading.value = false;
    }
  }

  async function deleteAgent(agentId: number): Promise<void> {
    loading.value = true;
    error.value = null;
    try {
      const res = await fetch(`${API}/agents/${agentId}`, {
        method: 'DELETE',
      });
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || 'Erro ao deletar agente.');
      }
      await fetchAgents();
      if (activeAgentId.value === agentId) {
        activeAgentId.value = agents.value[0]?.id || null;
      }
    } catch (err: any) {
      console.error('Erro ao deletar agente:', err);
      error.value = err.message;
      throw err;
    } finally {
      loading.value = false;
    }
  }

  async function setDefaultAgent(agentId: number): Promise<void> {
    try {
      const res = await fetch(`${API}/agents/${agentId}/set-default`, {
        method: 'POST',
      });
      if (!res.ok) throw new Error('Erro ao definir agente padrão.');
      await fetchAgents();
      activeAgentId.value = agentId;
    } catch (err: any) {
      console.error('Erro ao definir padrão:', err);
    }
  }

  return {
    agents,
    activeAgentId,
    activeAgent,
    loading,
    rewriting,
    reasoningText,
    reasoningStage,
    isReasoningExpanded,
    error,
    fetchAgents,
    setActiveAgentId,
    executeRewrite,
    executeRewriteStream,
    executeRewriteFeedbackStream,
    createAgentWithAI,
    startBuilderSession,
    sendBuilderMessage,
    resetBuilderSession,
    saveAgent,
    deleteAgent,
    setDefaultAgent,
  };
}
