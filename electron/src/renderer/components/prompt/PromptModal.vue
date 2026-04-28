<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      @click.self="close"
    >
      <div class="glass-surface rounded-2xl w-full max-w-xl max-h-[85vh] flex flex-col p-6 gap-4 shadow-2xl">
        <!-- Header -->
        <div class="flex items-center justify-between">
          <h2 class="text-lg font-plus-jakarta font-bold text-text-primary">{{ t('prompt.title') }}</h2>
          <button @click="close" class="text-text-muted hover:text-text-primary transition-colors">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <!-- Prompt name (read-only display) -->
        <div>
          <label class="block text-xs text-text-muted font-plus-jakarta font-medium mb-1">{{ t('prompt.name_label') }}</label>
          <input
            v-model="nome"
            type="text"
            :placeholder="t('prompt.name_placeholder')"
            class="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-text-primary placeholder:text-text-muted/50 font-plus-jakarta focus:outline-none focus:border-accent-blue/50"
          />
        </div>

        <!-- System prompt text -->
        <div class="flex-1 min-h-0">
          <label class="block text-xs text-text-muted font-plus-jakarta font-medium mb-1">{{ t('prompt.text_label') }}</label>
          <textarea
            v-model="textoPrompt"
            class="w-full h-40 bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-text-primary placeholder:text-text-muted/50 font-plus-jakarta resize-none focus:outline-none focus:border-accent-blue/50"
          ></textarea>
        </div>

        <!-- Keywords / Glossary -->
        <div>
          <label class="block text-xs text-text-muted font-plus-jakarta font-medium mb-1">{{ t('prompt.glossary_label') }}</label>
          <div class="flex gap-2 mb-2">
            <input
              v-model="newKeyword"
              type="text"
              :placeholder="t('prompt.add_keyword_placeholder')"
              class="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-sm text-text-primary placeholder:text-text-muted/50 font-plus-jakarta focus:outline-none focus:border-accent-blue/50"
              @keydown.enter.prevent="addKeyword"
            />
            <button @click="addKeyword" class="glass-btn text-xs px-3 py-1.5 text-accent-blue">+</button>
          </div>
          <div class="flex flex-wrap gap-2 max-h-24 overflow-y-auto">
            <span
              v-for="kw in keywords"
              :key="kw"
              class="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-accent-blue/15 text-accent-blue text-xs font-plus-jakarta"
            >
              {{ kw }}
              <button @click="removeKeyword(kw)" class="hover:text-red-400 transition-colors">&times;</button>
            </span>
            <span v-if="keywords.length === 0" class="text-xs text-text-muted italic">Nenhuma palavra-chave cadastrada</span>
          </div>
        </div>

        <!-- Actions -->
        <div class="flex items-center gap-3">
          <span v-if="saved" class="text-xs text-green-400 font-plus-jakarta">{{ t('prompt.saved') }}</span>
          <div class="flex-1"></div>
          <button @click="close" class="glass-btn text-xs px-4 py-2 text-text-muted">Cancelar</button>
          <button @click="save" class="bg-accent-blue/20 text-accent-blue px-4 py-2 rounded-lg text-xs font-plus-jakarta font-semibold hover:bg-accent-blue/30 transition-colors">
            {{ t('prompt.save') }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue';
import { t } from '../../i18n';

const props = defineProps<{ visible: boolean }>();
const emit = defineEmits<{ close: [] }>();

const nome = ref('');
const textoPrompt = ref('');
const keywords = ref<string[]>([]);
const newKeyword = ref('');
const saved = ref(false);

const API = 'http://localhost:18763';

async function load() {
  try {
    const res = await fetch(`${API}/prompt/default`);
    if (!res.ok) return;
    const data = await res.json();
    nome.value = data.nome || '';
    textoPrompt.value = data.texto_prompt || '';
    keywords.value = data.keywords || [];
  } catch {
    // API not available — leave empty
  }
}

async function save() {
  try {
    const res = await fetch(`${API}/prompt/default`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        nome: nome.value,
        texto_prompt: textoPrompt.value,
        keywords: keywords.value,
      }),
    });
    if (res.ok) {
      saved.value = true;
      setTimeout(() => (saved.value = false), 2000);
    }
  } catch {
    // Silently fail
  }
}

function addKeyword() {
  const kw = newKeyword.value.trim();
  if (kw && !keywords.value.includes(kw)) {
    keywords.value.push(kw);
  }
  newKeyword.value = '';
}

function removeKeyword(kw: string) {
  keywords.value = keywords.value.filter(k => k !== kw);
}

function close() {
  emit('close');
}

// Load data when modal opens
watch(() => props.visible, (v) => {
  if (v) load();
});
</script>
