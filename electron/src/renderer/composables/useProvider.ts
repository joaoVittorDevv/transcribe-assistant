import { ref } from 'vue';

/**
 * useProvider - Shared provider selection state
 * 
 * Provider modes:
 * - 'auto': Try Groq first, fallback to Google
 * - 'google': Google Gemini only
 * - 'groq': Groq Whisper only (not recommended for long audio)
 */

export type ProviderMode = 'auto' | 'google' | 'groq';

// Module-level state (singleton per app)
const selectedProvider = ref<ProviderMode>('auto');

export function useProvider() {
  return {
    selectedProvider,
    setProvider: (mode: ProviderMode) => {
      selectedProvider.value = mode;
    },
  };
}
