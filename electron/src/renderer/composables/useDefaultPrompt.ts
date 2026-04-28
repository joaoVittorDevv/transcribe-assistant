import { ref, onMounted } from 'vue';

interface DefaultPrompt {
  id: number | null;
  nome: string;
  texto_prompt: string;
  keywords: string[];
}

const promptRef = ref<DefaultPrompt>({
  id: null,
  nome: '',
  texto_prompt: '',
  keywords: [],
});

const API = 'http://localhost:18763';

export function useDefaultPrompt() {
  async function fetchPrompt() {
    try {
      const res = await fetch(`${API}/prompt/default`);
      if (res.ok) {
        promptRef.value = await res.json();
      }
    } catch {
      // API not available — use defaults
    }
  }

  // Fetch on first use
  if (!promptRef.value.id && !promptRef.value.nome) {
    fetchPrompt();
  }

  return {
    promptData: promptRef,
    fetchPrompt,
  };
}
