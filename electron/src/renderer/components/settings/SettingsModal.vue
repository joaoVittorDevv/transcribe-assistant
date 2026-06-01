<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      @click.self="close"
    >
      <div class="glass-surface rounded-2xl w-full max-w-2xl max-h-[85vh] flex flex-col p-6 gap-4 shadow-2xl">
        <!-- Header -->
        <div class="flex items-center justify-between border-b border-white/5 pb-2">
          <div class="flex items-center gap-6">
            <h2 class="text-lg font-plus-jakarta font-bold text-text-primary">
              {{ activeTab === 'prompt' ? t('prompt.title') : t('settings.tabs.general') }}
            </h2>
            <!-- Tab Navigation -->
            <div class="flex gap-4">
              <button
                @click="activeTab = 'prompt'"
                :class="[
                  'text-xs font-plus-jakarta font-semibold pb-1 border-b-2 transition-all duration-200',
                  activeTab === 'prompt'
                    ? 'border-accent-blue text-accent-blue'
                    : 'border-transparent text-text-muted hover:text-text-primary'
                ]"
              >
                {{ t('settings.tabs.prompt') }}
              </button>
              <button
                @click="activeTab = 'general'"
                :class="[
                  'text-xs font-plus-jakarta font-semibold pb-1 border-b-2 transition-all duration-200',
                  activeTab === 'general'
                    ? 'border-accent-blue text-accent-blue'
                    : 'border-transparent text-text-muted hover:text-text-primary'
                ]"
              >
                {{ t('settings.tabs.general') }}
              </button>
            </div>
          </div>
          <button @click="close" class="text-text-muted hover:text-text-primary transition-colors">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <!-- Scrollable content area -->
        <div class="flex-1 overflow-y-auto pr-1 flex flex-col gap-4">
          <!-- ABA 1: PROMPT DO SISTEMA -->
          <div v-if="activeTab === 'prompt'" class="flex flex-col gap-4">
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
            <div>
              <label class="block text-xs text-text-muted font-plus-jakarta font-medium mb-1">{{ t('prompt.text_label') }}</label>
              <textarea
                v-model="textoPrompt"
                class="w-full h-44 bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-text-primary placeholder:text-text-muted/50 font-plus-jakarta resize-none focus:outline-none focus:border-accent-blue/50"
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
                  class="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-accent-blue/15 text-accent-blue text-xs font-plus-jakarta animate-fade-in"
                >
                  {{ kw }}
                  <button @click="removeKeyword(kw)" class="hover:text-red-400 transition-colors">&times;</button>
                </span>
                <span v-if="keywords.length === 0" class="text-xs text-text-muted italic">Nenhuma palavra-chave cadastrada</span>
              </div>
            </div>
          </div>

          <!-- ABA 2: CONFIGURAÇÕES GERAIS -->
          <div v-else-if="activeTab === 'general'" class="flex flex-col gap-4">
            <!-- Google Gemini Settings -->
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4 border-b border-white/5 pb-4">
              <div>
                <label class="block text-xs text-text-muted font-plus-jakarta font-medium mb-1">
                  {{ t('settings.gemini_key') }}
                </label>
                <div class="relative">
                  <input
                    v-model="geminiKey"
                    :type="showGeminiKey ? 'text' : 'password'"
                    placeholder="AIzaSy..."
                    class="w-full bg-white/5 border border-white/10 rounded-lg pl-3 pr-10 py-2 text-sm text-text-primary placeholder:text-text-muted/50 font-plus-jakarta focus:outline-none focus:border-accent-blue/50"
                  />
                  <button
                    type="button"
                    @click="showGeminiKey = !showGeminiKey"
                    class="absolute inset-y-0 right-0 pr-3 flex items-center text-text-muted hover:text-text-primary"
                  >
                    <span class="text-xs font-semibold">{{ showGeminiKey ? 'Ocultar' : 'Revelar' }}</span>
                  </button>
                </div>
              </div>

              <div>
                <label class="block text-xs text-text-muted font-plus-jakarta font-medium mb-1">
                  {{ t('settings.gemini_model') }}
                </label>
                <select
                  v-model="geminiModel"
                  class="w-full bg-[#1A2332] border border-white/10 rounded-lg px-3 py-2 text-sm text-text-primary font-plus-jakarta focus:outline-none focus:border-accent-blue/50"
                >
                  <option v-for="model in geminiModelsList" :key="model" :value="model">
                    {{ model }}
                  </option>
                  <option v-if="geminiModelsList.length === 0" value="">
                    Nenhum modelo carregado
                  </option>
                </select>
              </div>
            </div>

            <!-- Groq Settings -->
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4 border-b border-white/5 pb-4">
              <div>
                <label class="block text-xs text-text-muted font-plus-jakarta font-medium mb-1">
                  {{ t('settings.groq_key') }}
                </label>
                <div class="relative">
                  <input
                    v-model="groqKey"
                    :type="showGroqKey ? 'text' : 'password'"
                    placeholder="gsk_..."
                    class="w-full bg-white/5 border border-white/10 rounded-lg pl-3 pr-10 py-2 text-sm text-text-primary placeholder:text-text-muted/50 font-plus-jakarta focus:outline-none focus:border-accent-blue/50"
                  />
                  <button
                    type="button"
                    @click="showGroqKey = !showGroqKey"
                    class="absolute inset-y-0 right-0 pr-3 flex items-center text-text-muted hover:text-text-primary"
                  >
                    <span class="text-xs font-semibold">{{ showGroqKey ? 'Ocultar' : 'Revelar' }}</span>
                  </button>
                </div>
              </div>

              <div>
                <label class="block text-xs text-text-muted font-plus-jakarta font-medium mb-1">
                  {{ t('settings.groq_model') }}
                </label>
                <select
                  v-model="groqModel"
                  class="w-full bg-[#1A2332] border border-white/10 rounded-lg px-3 py-2 text-sm text-text-primary font-plus-jakarta focus:outline-none focus:border-accent-blue/50"
                >
                  <option v-for="model in groqModelsList" :key="model" :value="model">
                    {{ model }}
                  </option>
                  <option v-if="groqModelsList.length === 0" value="">
                    Nenhum modelo carregado
                  </option>
                </select>
              </div>
            </div>

            <!-- Fetch Models Control -->
            <div class="flex justify-end -mt-2">
              <button
                @click="fetchModels"
                :disabled="loadingModels"
                class="glass-btn text-xs px-4 py-1.5 flex items-center gap-2 hover:bg-white/5 transition-colors disabled:opacity-50"
              >
                <svg
                  v-if="loadingModels"
                  class="animate-spin h-3 w-3 text-accent-blue"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <span>{{ loadingModels ? t('settings.fetching') : t('settings.fetch_models') }}</span>
              </button>
            </div>

            <!-- Directory Paths -->
            <div class="flex flex-col gap-3 border-b border-white/5 pb-4">
              <div>
                <label class="block text-xs text-text-muted font-plus-jakarta font-medium mb-1">
                  {{ t('settings.vault_path') }}
                </label>
                <div class="flex gap-2">
                  <input
                    v-model="vaultPath"
                    type="text"
                    readonly
                    class="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-xs text-text-muted font-plus-jakarta focus:outline-none select-all"
                  />
                  <button @click="selectVaultPath" class="glass-btn text-xs px-3 py-2 text-accent-blue whitespace-nowrap">
                    {{ t('settings.select_dir') }}
                  </button>
                </div>
              </div>

              <div>
                <label class="block text-xs text-text-muted font-plus-jakarta font-medium mb-1">
                  {{ t('settings.dual_path') }}
                </label>
                <div class="flex gap-2">
                  <input
                    v-model="dualPath"
                    type="text"
                    readonly
                    class="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-xs text-text-muted font-plus-jakarta focus:outline-none select-all"
                  />
                  <button @click="selectDualPath" class="glass-btn text-xs px-3 py-2 text-accent-blue whitespace-nowrap">
                    {{ t('settings.select_dir') }}
                  </button>
                </div>
              </div>
            </div>

            <!-- Network & Language settings -->
            <div>
              <h3 class="text-xs font-plus-jakarta font-bold text-text-primary mb-3">
                {{ t('settings.network') }} &amp; {{ t('settings.language') }}
              </h3>
              <div class="grid grid-cols-1 sm:grid-cols-4 gap-4">
                <div class="sm:col-span-2">
                  <label class="block text-xs text-text-muted font-plus-jakarta font-medium mb-1">
                    {{ t('settings.host') }}
                  </label>
                  <input
                    v-model="networkHost"
                    type="text"
                    class="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-text-primary font-plus-jakarta focus:outline-none focus:border-accent-blue/50"
                  />
                </div>

                <div>
                  <label class="block text-xs text-text-muted font-plus-jakarta font-medium mb-1">
                    {{ t('settings.port') }}
                  </label>
                  <input
                    v-model="networkPort"
                    type="number"
                    class="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-text-primary font-plus-jakarta focus:outline-none focus:border-accent-blue/50"
                  />
                </div>

                <div>
                  <label class="block text-xs text-text-muted font-plus-jakarta font-medium mb-1">
                    {{ t('settings.language') }}
                  </label>
                  <select
                    v-model="appLanguage"
                    class="w-full bg-[#1A2332] border border-white/10 rounded-lg px-3 py-2 text-sm text-text-primary font-plus-jakarta focus:outline-none focus:border-accent-blue/50"
                  >
                    <option value="pt">Português</option>
                    <option value="en">English</option>
                  </select>
                </div>
              </div>

              <div class="mt-4">
                <label class="block text-xs text-text-muted font-plus-jakarta font-medium mb-1">
                  {{ t('settings.check_interval') }}
                </label>
                <input
                  v-model="networkCheckInterval"
                  type="number"
                  class="w-full max-w-[200px] bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-text-primary font-plus-jakarta focus:outline-none focus:border-accent-blue/50"
                />
              </div>
            </div>

            <!-- Alertas e Notificações (Silk Theme) -->
            <div class="border-t border-white/5 pt-4 flex flex-col gap-4">
              <h3 class="text-xs font-plus-jakarta font-bold text-text-primary">
                {{ t('settings.alerts.section_title') }}
              </h3>
              
              <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <!-- Toggle Tray -->
                <div class="flex items-center justify-between bg-white/5 p-3 rounded-lg border border-white/5">
                  <span class="text-xs text-text-muted font-plus-jakarta font-medium">
                    {{ t('settings.alerts.tray_enabled') }}
                  </span>
                  <label class="relative inline-flex items-center cursor-pointer">
                    <input type="checkbox" v-model="trayEnabled" class="sr-only peer" />
                    <div class="w-8 h-4 bg-white/10 rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-0.5 after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-3 after:w-3 after:transition-all peer-checked:bg-accent-blue"></div>
                  </label>
                </div>

                <!-- Toggle Notifications -->
                <div class="flex items-center justify-between bg-white/5 p-3 rounded-lg border border-white/5">
                  <span class="text-xs text-text-muted font-plus-jakarta font-medium">
                    {{ t('settings.alerts.notifications_enabled') }}
                  </span>
                  <label class="relative inline-flex items-center cursor-pointer">
                    <input type="checkbox" v-model="persistentNotificationsEnabled" class="sr-only peer" />
                    <div class="w-8 h-4 bg-white/10 rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-0.5 after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-3 after:w-3 after:transition-all peer-checked:bg-accent-blue"></div>
                  </label>
                </div>
              </div>

              <!-- Interval Slider -->
              <div class="bg-white/5 p-3 rounded-lg border border-white/5">
                <div class="flex justify-between items-center mb-2">
                  <label class="text-xs text-text-muted font-plus-jakarta font-medium">
                    {{ t('settings.alerts.interval_label') }}
                  </label>
                  <span class="text-xs text-accent-blue font-bold font-plus-jakarta">{{ alertInterval }}m</span>
                </div>
                <input
                  v-model="alertInterval"
                  type="range"
                  min="1"
                  max="60"
                  class="w-full h-1 bg-white/10 rounded-lg appearance-none cursor-pointer accent-accent-blue"
                />
              </div>

              <!-- Transcription Types -->
              <div class="bg-white/5 p-3 rounded-lg border border-white/5">
                <label class="block text-xs text-text-muted font-plus-jakarta font-medium mb-3">
                  {{ t('settings.alerts.types_label') }}
                </label>
                <div class="flex gap-6">
                  <label class="inline-flex items-center gap-2 text-xs text-text-muted font-plus-jakarta cursor-pointer">
                    <input
                      type="checkbox"
                      value="realtime"
                      v-model="alertTranscriptionTypes"
                      class="rounded bg-white/5 border-white/10 text-accent-blue focus:ring-accent-blue/30"
                    />
                    {{ t('settings.alerts.types_realtime') }}
                  </label>
                  <label class="inline-flex items-center gap-2 text-xs text-text-muted font-plus-jakarta cursor-pointer">
                    <input
                      type="checkbox"
                      value="file"
                      v-model="alertTranscriptionTypes"
                      class="rounded bg-white/5 border-white/10 text-accent-blue focus:ring-accent-blue/30"
                    />
                    {{ t('settings.alerts.types_file') }}
                  </label>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Actions -->
        <div class="flex items-center gap-3 border-t border-white/5 pt-3">
          <span v-if="saved" class="text-xs text-green-400 font-plus-jakarta animate-pulse">
            {{ t('settings.save_success') }}
          </span>
          <div class="flex-1"></div>
          <button @click="close" class="glass-btn text-xs px-4 py-2 text-text-muted">
            Cancelar
          </button>
          <button
            @click="save"
            class="bg-accent-blue/20 text-accent-blue px-4 py-2 rounded-lg text-xs font-plus-jakarta font-semibold hover:bg-accent-blue/30 transition-colors"
          >
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

// Tab Control
const activeTab = ref<'prompt' | 'general'>('prompt');

// Prompt Tab fields
const nome = ref('');
const textoPrompt = ref('');
const keywords = ref<string[]>([]);
const newKeyword = ref('');

// General Settings Tab fields
const geminiKey = ref('');
const geminiModel = ref('');
const groqKey = ref('');
const groqModel = ref('');
const vaultPath = ref('');
const dualPath = ref('');
const networkHost = ref('');
const networkPort = ref<number | string>('');
const networkCheckInterval = ref<number | string>('');
const appLanguage = ref('pt');

// Tray & Notification Settings refs
const trayEnabled = ref(false);
const persistentNotificationsEnabled = ref(true);
const alertInterval = ref(15);
const alertTranscriptionTypes = ref<string[]>(['realtime']);

// Key Visibility
const showGeminiKey = ref(false);
const showGroqKey = ref(false);

// Models Lists
const loadingModels = ref(false);
const geminiModelsList = ref<string[]>([]);
const groqModelsList = ref<string[]>([]);

const saved = ref(false);
const API = 'http://localhost:18763';

// Load prompt configuration
async function loadPrompt() {
  try {
    const res = await fetch(`${API}/prompt/default`);
    if (!res.ok) return;
    const data = await res.json();
    nome.value = data.nome || '';
    textoPrompt.value = data.texto_prompt || '';
    keywords.value = data.keywords || [];
  } catch (err) {
    console.error('Erro ao buscar prompt:', err);
  }
}

// Load general configurations and fetch models
async function loadSettings() {
  try {
    const res = await fetch(`${API}/settings`);
    if (!res.ok) return;
    const data = await res.json();
    geminiKey.value = data.gemini_key_masked || '';
    geminiModel.value = data.gemini_model || '';
    groqKey.value = data.groq_key_masked || '';
    groqModel.value = data.groq_review_model || '';
    vaultPath.value = data.vault_path || '';
    dualPath.value = data.dual_intermediary_path || '';
    networkHost.value = data.network_ping_host || '';
    networkPort.value = data.network_ping_port;
    networkCheckInterval.value = data.network_check_interval;
    appLanguage.value = data.app_language || 'pt';

    // Load alerts and tray states
    trayEnabled.value = data.tray_enabled ?? false;
    persistentNotificationsEnabled.value = data.persistent_notifications_enabled ?? true;
    alertInterval.value = data.alert_interval ?? 15;
    const alertTypes = data.alert_transcription_types || 'realtime';
    alertTranscriptionTypes.value = alertTypes.split(',').filter(Boolean);

    // Fetch lists of models
    await fetchModels();
  } catch (err) {
    console.error('Erro ao buscar configurações:', err);
  }
}

// Dynamically fetch models
async function fetchModels() {
  loadingModels.value = true;
  try {
    const res = await fetch(`${API}/settings/models`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        gemini_key: geminiKey.value,
        groq_key: groqKey.value,
      }),
    });
    if (res.ok) {
      const data = await res.json();
      geminiModelsList.value = data.gemini_models || [];
      groqModelsList.value = data.groq_models || [];

      // Append saved model if not returned by list
      if (geminiModel.value && !geminiModelsList.value.includes(geminiModel.value)) {
        geminiModelsList.value.unshift(geminiModel.value);
      }
      if (groqModel.value && !groqModelsList.value.includes(groqModel.value)) {
        groqModelsList.value.unshift(groqModel.value);
      }
    }
  } catch (err) {
    console.error('Erro ao buscar lista de modelos:', err);
  } finally {
    loadingModels.value = false;
  }
}

// File selectors using Electron IPC
async function selectVaultPath() {
  if (window.electronAPI && window.electronAPI.openDirectoryPicker) {
    const path = await window.electronAPI.openDirectoryPicker();
    if (path) {
      vaultPath.value = path;
    }
  }
}

async function selectDualPath() {
  if (window.electronAPI && window.electronAPI.openDirectoryPicker) {
    const path = await window.electronAPI.openDirectoryPicker();
    if (path) {
      dualPath.value = path;
    }
  }
}

// Save all configurations
async function save() {
  try {
    // 1. Save system prompt
    const promptRes = await fetch(`${API}/prompt/default`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        nome: nome.value,
        texto_prompt: textoPrompt.value,
        keywords: keywords.value,
      }),
    });

    // 2. Save general settings
    const settingsRes = await fetch(`${API}/settings`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        gemini_key: geminiKey.value,
        gemini_model: geminiModel.value,
        groq_key: groqKey.value,
        groq_review_model: groqModel.value,
        app_language: appLanguage.value,
        vault_path: vaultPath.value,
        dual_intermediary_path: dualPath.value,
        network_ping_host: networkHost.value,
        network_ping_port: parseInt(String(networkPort.value)) || 18763,
        network_check_interval: parseInt(String(networkCheckInterval.value)) || 5000,
        tray_enabled: trayEnabled.value,
        persistent_notifications_enabled: persistentNotificationsEnabled.value,
        alert_interval: parseInt(String(alertInterval.value)) || 15,
        alert_transcription_types: alertTranscriptionTypes.value.join(','),
      }),
    });

    if (promptRes.ok && settingsRes.ok) {
      // Notify electron main process
      if (window.electronAPI && window.electronAPI.updateSettingsTray) {
        window.electronAPI.updateSettingsTray({
          enabled: trayEnabled.value,
          notificationsEnabled: persistentNotificationsEnabled.value,
          interval: parseInt(String(alertInterval.value)) || 15,
          types: alertTranscriptionTypes.value.join(',')
        });
      }

      saved.value = true;
      setTimeout(() => {
        saved.value = false;
        close();
      }, 1500);
    }
  } catch (err) {
    console.error('Erro ao salvar as configurações gerais:', err);
  }
}

// Keywords list helpers
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

// Refresh settings and prompt when visible
watch(() => props.visible, (v) => {
  if (v) {
    activeTab.value = 'prompt'; // Default tab on open
    showGeminiKey.value = false;
    showGroqKey.value = false;
    loadPrompt();
    loadSettings();
  }
});
</script>
