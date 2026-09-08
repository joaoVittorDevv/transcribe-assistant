<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 font-inter select-none"
      @click.self="close"
    >
      <div class="bg-[#16181F] border border-[#2D3342] rounded-xl w-full max-w-4xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden animate-slide-in">
        <!-- Top Modal Header -->
        <div class="flex items-center justify-between px-6 py-4 border-b border-[#2D3342] bg-[#1A1D24]/70 flex-shrink-0">
          <div class="flex items-center gap-3">
            <div class="w-8 h-8 rounded-lg bg-[#222733] border border-[#3F444E] flex items-center justify-center text-[#F59E0B] shadow-sm">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.75" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.75" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
            </div>
            <div>
              <h2 class="text-sm font-bold text-[#DDE2F6] leading-tight">Configurações &amp; Orquestração</h2>
              <p class="text-[11px] text-[#909095] font-medium leading-tight">Painel Bento de Ajustes e Prompts de Transcrição</p>
            </div>
          </div>
          <button
            @click="close"
            class="text-[#909095] hover:text-[#DDE2F6] p-1 rounded hover:bg-[#222733] transition-colors"
            title="Fechar"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <!-- Body: Vertical Tabs Sidebar + Content Bento Panels -->
        <div class="flex-1 flex min-h-0 overflow-hidden">
          <!-- Inner Nav Sidebar -->
          <div class="w-52 border-r border-[#2D3342] bg-[#16181F] p-3 flex flex-col gap-1 flex-shrink-0">
            <button
              @click="activeTab = 'prompt'"
              :class="[
                'flex items-center gap-2.5 px-3 py-2 rounded-md text-xs font-medium transition-colors text-left w-full',
                activeTab === 'prompt'
                  ? 'bg-[#222733] text-[#F59E0B] border border-[#3F444E]/60 shadow-sm'
                  : 'text-[#909095] hover:text-[#DDE2F6] hover:bg-[#1A1D24]'
              ]"
            >
              <svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.75" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>
              <span>Prompt &amp; Glossário</span>
            </button>

            <button
              @click="activeTab = 'providers'"
              :class="[
                'flex items-center gap-2.5 px-3 py-2 rounded-md text-xs font-medium transition-colors text-left w-full',
                activeTab === 'providers'
                  ? 'bg-[#222733] text-[#F59E0B] border border-[#3F444E]/60 shadow-sm'
                  : 'text-[#909095] hover:text-[#DDE2F6] hover:bg-[#1A1D24]'
              ]"
            >
              <svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.75" d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              <span>Provedores de IA</span>
            </button>

            <button
              @click="activeTab = 'agents'"
              :class="[
                'flex items-center gap-2.5 px-3 py-2 rounded-md text-xs font-medium transition-colors text-left w-full',
                activeTab === 'agents'
                  ? 'bg-[#222733] text-[#F59E0B] border border-[#3F444E]/60 shadow-sm'
                  : 'text-[#909095] hover:text-[#DDE2F6] hover:bg-[#1A1D24]'
              ]"
            >
              <svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.75" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
              </svg>
              <span>Agentes de Reescrita</span>
            </button>

            <button
              @click="activeTab = 'storage'"
              :class="[
                'flex items-center gap-2.5 px-3 py-2 rounded-md text-xs font-medium transition-colors text-left w-full',
                activeTab === 'storage'
                  ? 'bg-[#222733] text-[#F59E0B] border border-[#3F444E]/60 shadow-sm'
                  : 'text-[#909095] hover:text-[#DDE2F6] hover:bg-[#1A1D24]'
              ]"
            >
              <svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.75" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
              </svg>
              <span>Armazenamento &amp; Vault</span>
            </button>

            <button
              @click="activeTab = 'tray'"
              :class="[
                'flex items-center gap-2.5 px-3 py-2 rounded-md text-xs font-medium transition-colors text-left w-full',
                activeTab === 'tray'
                  ? 'bg-[#222733] text-[#F59E0B] border border-[#3F444E]/60 shadow-sm'
                  : 'text-[#909095] hover:text-[#DDE2F6] hover:bg-[#1A1D24]'
              ]"
            >
              <svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.75" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
              </svg>
              <span>Bandeja &amp; Alertas</span>
            </button>

            <button
              @click="activeTab = 'network'"
              :class="[
                'flex items-center gap-2.5 px-3 py-2 rounded-md text-xs font-medium transition-colors text-left w-full',
                activeTab === 'network'
                  ? 'bg-[#222733] text-[#F59E0B] border border-[#3F444E]/60 shadow-sm'
                  : 'text-[#909095] hover:text-[#DDE2F6] hover:bg-[#1A1D24]'
              ]"
            >
              <svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.75" d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
              </svg>
              <span>Rede &amp; Idioma</span>
            </button>
          </div>

          <!-- Content Bento Area -->
          <div class="flex-1 p-5 overflow-y-auto bg-[#13151A] select-text">
            <!-- TAB: PROMPT & GLOSSÁRIO -->
            <div v-if="activeTab === 'prompt'" class="flex flex-col gap-4">
              <!-- System Prompt Card -->
              <div class="bento-card p-4 flex flex-col gap-3">
                <div class="flex items-center justify-between">
                  <span class="text-xs font-bold text-[#DDE2F6]">Engenharia do Prompt Mestre</span>
                  <span class="text-[10px] text-[#909095] font-mono">YAML / Markdown</span>
                </div>

                <div>
                  <label class="block text-[11px] text-[#909095] font-medium mb-1">Nome do Perfil de Prompt</label>
                  <input
                    v-model="nome"
                    type="text"
                    :placeholder="t('prompt.name_placeholder')"
                    class="bento-input w-full py-1.5 px-3 text-xs"
                  />
                </div>

                <div>
                  <div class="flex items-center justify-between mb-1">
                    <label class="block text-[11px] text-[#909095] font-medium">Instrução do Sistema (Prompt Direto)</label>
                    <div class="flex items-center gap-1.5">
                      <button
                        @click="insertPromptVariable('@Usuario: ')"
                        class="text-[10px] text-[#3B82F6] hover:text-[#60A5FA] bg-[#3B82F6]/10 border border-[#3B82F6]/30 px-1.5 py-0.5 rounded transition-colors"
                      >+ @Usuario</button>
                      <button
                        @click="insertPromptVariable('@Interlocutor: ')"
                        class="text-[10px] text-[#F59E0B] hover:text-[#FBBF24] bg-[#F59E0B]/10 border border-[#F59E0B]/30 px-1.5 py-0.5 rounded transition-colors"
                      >+ @Interlocutor</button>
                    </div>
                  </div>
                  <textarea
                    v-model="textoPrompt"
                    rows="6"
                    class="bento-input w-full p-3 font-mono text-xs text-[#DDE2F6] leading-relaxed resize-none"
                    placeholder="Defina as regras de transcrição, diarização e formatação da IA..."
                  ></textarea>
                </div>
              </div>

              <!-- Glossary Card -->
              <div class="bento-card p-4 flex flex-col gap-3">
                <div class="flex items-center justify-between">
                  <span class="text-xs font-bold text-[#DDE2F6]">Glossário de Reconhecimento &amp; Termos Raros</span>
                  <span class="text-[10px] text-[#909095] font-mono">{{ keywords.length }} cadastrados</span>
                </div>

                <div class="flex gap-2">
                  <input
                    v-model="newKeyword"
                    type="text"
                    :placeholder="t('prompt.add_keyword_placeholder')"
                    class="bento-input flex-1 py-1.5 px-3 text-xs"
                    @keydown.enter.prevent="addKeyword"
                  />
                  <button @click="addKeyword" class="bento-btn px-3 py-1.5 text-xs text-[#F59E0B] font-semibold">
                    Adicionar
                  </button>
                </div>

                <div class="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto p-2 bg-[#13151A] rounded border border-[#2D3342]">
                  <span
                    v-for="kw in keywords"
                    :key="kw"
                    class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-[#222733] text-[#DDE2F6] border border-[#3F444E] text-[11px] font-mono shadow-sm"
                  >
                    {{ kw }}
                    <button @click="removeKeyword(kw)" class="text-[#909095] hover:text-[#EF4444] transition-colors ml-0.5">&times;</button>
                  </span>
                  <span v-if="keywords.length === 0" class="text-xs text-[#909095] italic">Nenhuma palavra-chave cadastrada</span>
                </div>
              </div>
            </div>

            <!-- TAB: PROVEDORES DE IA -->
            <div v-else-if="activeTab === 'providers'" class="flex flex-col gap-4">
              <!-- Google Gemini Card -->
              <div class="bento-card p-4 flex flex-col gap-3">
                <div class="flex items-center justify-between border-b border-[#2D3342] pb-2">
                  <div class="flex items-center gap-2">
                    <span class="w-2 h-2 rounded-full bg-[#3B82F6]"></span>
                    <span class="text-xs font-bold text-[#DDE2F6]">Google Gemini API</span>
                  </div>
                  <span class="text-[10px] text-[#3B82F6] font-mono">Tempo Real &amp; Áudio de Sistema</span>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label class="block text-[11px] text-[#909095] font-medium mb-1">Chave de API Gemini</label>
                    <div class="relative">
                      <input
                        v-model="geminiKey"
                        :type="showGeminiKey ? 'text' : 'password'"
                        placeholder="AIzaSy..."
                        class="bento-input w-full pl-3 pr-16 py-1.5 text-xs font-mono"
                      />
                      <button
                        type="button"
                        @click="showGeminiKey = !showGeminiKey"
                        class="absolute inset-y-0 right-0 pr-2.5 flex items-center text-[10px] text-[#909095] hover:text-[#DDE2F6]"
                      >
                        {{ showGeminiKey ? 'Ocultar' : 'Revelar' }}
                      </button>
                    </div>
                  </div>

                  <div>
                    <label class="block text-[11px] text-[#909095] font-medium mb-1">Modelo Selecionado</label>
                    <select
                      v-model="geminiModel"
                      class="bento-input w-full px-3 py-1.5 text-xs font-mono bg-[#13151A]"
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
              </div>

              <!-- Groq Whisper Card -->
              <div class="bento-card p-4 flex flex-col gap-3">
                <div class="flex items-center justify-between border-b border-[#2D3342] pb-2">
                  <div class="flex items-center gap-2">
                    <span class="w-2 h-2 rounded-full bg-[#F59E0B]"></span>
                    <span class="text-xs font-bold text-[#DDE2F6]">Groq Whisper &amp; Review</span>
                  </div>
                  <span class="text-[10px] text-[#F59E0B] font-mono">Microfone &amp; Alta Velocidade</span>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label class="block text-[11px] text-[#909095] font-medium mb-1">Chave de API Groq</label>
                    <div class="relative">
                      <input
                        v-model="groqKey"
                        :type="showGroqKey ? 'text' : 'password'"
                        placeholder="gsk_..."
                        class="bento-input w-full pl-3 pr-16 py-1.5 text-xs font-mono"
                      />
                      <button
                        type="button"
                        @click="showGroqKey = !showGroqKey"
                        class="absolute inset-y-0 right-0 pr-2.5 flex items-center text-[10px] text-[#909095] hover:text-[#DDE2F6]"
                      >
                        {{ showGroqKey ? 'Ocultar' : 'Revelar' }}
                      </button>
                    </div>
                  </div>

                  <div>
                    <label class="block text-[11px] text-[#909095] font-medium mb-1">Modelo de Revisão / Transcrição</label>
                    <select
                      v-model="groqModel"
                      class="bento-input w-full px-3 py-1.5 text-xs font-mono bg-[#13151A]"
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
              </div>

              <!-- MiniMax Card (Coding Plan / Meta-Agent) -->
              <div class="bento-card p-4 flex flex-col gap-3">
                <div class="flex items-center justify-between border-b border-[#2D3342] pb-2">
                  <div class="flex items-center gap-2">
                    <span class="w-2 h-2 rounded-full bg-[#10B981]"></span>
                    <span class="text-xs font-bold text-[#DDE2F6]">MiniMax (Coding Plan)</span>
                  </div>
                  <span class="text-[10px] text-[#10B981] font-mono">Meta-Agente &amp; Reestruturação de Texto</span>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <div>
                    <label class="block text-[11px] text-[#909095] font-medium mb-1">Chave de API MiniMax</label>
                    <div class="relative">
                      <input
                        v-model="minimaxKey"
                        :type="showMinimaxKey ? 'text' : 'password'"
                        placeholder="sk-..."
                        class="bento-input w-full pl-3 pr-16 py-1.5 text-xs font-mono"
                      />
                      <button
                        type="button"
                        @click="showMinimaxKey = !showMinimaxKey"
                        class="absolute inset-y-0 right-0 pr-2.5 flex items-center text-[10px] text-[#909095] hover:text-[#DDE2F6]"
                      >
                        {{ showMinimaxKey ? 'Ocultar' : 'Revelar' }}
                      </button>
                    </div>
                  </div>

                  <div>
                    <label class="block text-[11px] text-[#909095] font-medium mb-1">Base URL (Endpoint)</label>
                    <input
                      v-model="minimaxBaseUrl"
                      type="text"
                      placeholder="https://api.minimax.io/v1"
                      class="bento-input w-full px-3 py-1.5 text-xs font-mono"
                    />
                  </div>

                  <div>
                    <label class="block text-[11px] text-[#909095] font-medium mb-1">Modelo MiniMax</label>
                    <select
                      v-model="minimaxModel"
                      class="bento-input w-full px-3 py-1.5 text-xs font-mono bg-[#13151A]"
                    >
                      <option v-for="model in minimaxModelsList" :key="model" :value="model">
                        {{ model }}
                      </option>
                      <option v-if="minimaxModelsList.length === 0" value="">
                        Nenhum modelo carregado
                      </option>
                    </select>
                  </div>
                </div>
              </div>

              <!-- Sync Models Action Button -->
              <div class="flex justify-end">
                <button
                  @click="fetchModels"
                  :disabled="loadingModels"
                  class="bento-btn py-1.5 px-3 text-xs flex items-center gap-2 text-[#DDE2F6]"
                >
                  <svg
                    v-if="loadingModels"
                    class="animate-spin h-3.5 w-3.5 text-[#F59E0B]"
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  <span>{{ loadingModels ? t('settings.fetching') : 'Atualizar Lista de Modelos Dinâmicos' }}</span>
                </button>
              </div>
            </div>

            <!-- TAB: AGENTES DE REESCRITA -->
            <AgentsSettingsTab v-else-if="activeTab === 'agents'" />

            <!-- TAB: ARMAZENAMENTO & VAULT -->
            <div v-else-if="activeTab === 'storage'" class="flex flex-col gap-4">
              <div class="bento-card p-4 flex flex-col gap-3">
                <span class="text-xs font-bold text-[#DDE2F6]">Diretórios de Gravação &amp; Vault Local</span>

                <div>
                  <label class="block text-[11px] text-[#909095] font-medium mb-1">{{ t('settings.vault_path') }}</label>
                  <div class="flex gap-2">
                    <input
                      v-model="vaultPath"
                      type="text"
                      readonly
                      class="bento-input flex-1 py-1.5 px-3 text-xs text-[#909095] font-mono select-all"
                    />
                    <button @click="selectVaultPath" class="bento-btn text-xs px-3 py-1.5 text-[#3B82F6]">
                      {{ t('settings.select_dir') }}
                    </button>
                  </div>
                </div>

                <div>
                  <label class="block text-[11px] text-[#909095] font-medium mb-1">{{ t('settings.dual_path') }}</label>
                  <div class="flex gap-2">
                    <input
                      v-model="dualPath"
                      type="text"
                      readonly
                      class="bento-input flex-1 py-1.5 px-3 text-xs text-[#909095] font-mono select-all"
                    />
                    <button @click="selectDualPath" class="bento-btn text-xs px-3 py-1.5 text-[#3B82F6]">
                      {{ t('settings.select_dir') }}
                    </button>
                  </div>
                </div>
              </div>
            </div>

            <!-- TAB: BANDEJA & ALERTAS -->
            <div v-else-if="activeTab === 'tray'" class="flex flex-col gap-4">
              <div class="bento-card p-4 flex flex-col gap-4">
                <span class="text-xs font-bold text-[#DDE2F6]">Comportamento em Segundo Plano &amp; Alertas</span>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <!-- Toggle Tray -->
                  <div class="flex items-center justify-between bg-[#13151A] p-3 rounded border border-[#2D3342]">
                    <div class="flex flex-col">
                      <span class="text-xs text-[#DDE2F6] font-medium">{{ t('settings.alerts.tray_enabled') }}</span>
                      <span class="text-[10px] text-[#909095]">Minimizar para a barra de tarefas</span>
                    </div>
                    <label class="relative inline-flex items-center cursor-pointer">
                      <input type="checkbox" v-model="trayEnabled" class="sr-only peer" />
                      <div class="w-8 h-4 bg-[#222733] rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-0.5 after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-3 after:w-3 after:transition-all peer-checked:bg-[#F59E0B]"></div>
                    </label>
                  </div>

                  <!-- Toggle Notifications -->
                  <div class="flex items-center justify-between bg-[#13151A] p-3 rounded border border-[#2D3342]">
                    <div class="flex flex-col">
                      <span class="text-xs text-[#DDE2F6] font-medium">{{ t('settings.alerts.notifications_enabled') }}</span>
                      <span class="text-[10px] text-[#909095]">Lembretes de gravação em andamento</span>
                    </div>
                    <label class="relative inline-flex items-center cursor-pointer">
                      <input type="checkbox" v-model="persistentNotificationsEnabled" class="sr-only peer" />
                      <div class="w-8 h-4 bg-[#222733] rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-0.5 after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-3 after:w-3 after:transition-all peer-checked:bg-[#F59E0B]"></div>
                    </label>
                  </div>
                </div>

                <!-- Interval Slider -->
                <div class="bg-[#13151A] p-3 rounded border border-[#2D3342] flex flex-col gap-2">
                  <div class="flex justify-between items-center">
                    <label class="text-xs text-[#DDE2F6] font-medium">{{ t('settings.alerts.interval_label') }}</label>
                    <span class="text-xs text-[#F59E0B] font-mono font-bold">{{ alertInterval }} minutos</span>
                  </div>
                  <input
                    v-model="alertInterval"
                    type="range"
                    min="1"
                    max="60"
                    class="w-full h-1 bg-[#222733] rounded appearance-none cursor-pointer accent-[#F59E0B]"
                  />
                </div>

                <!-- Transcription Types -->
                <div class="bg-[#13151A] p-3 rounded border border-[#2D3342] flex flex-col gap-2">
                  <label class="text-xs text-[#DDE2F6] font-medium">{{ t('settings.alerts.types_label') }}</label>
                  <div class="flex gap-6">
                    <label class="inline-flex items-center gap-2 text-xs text-[#909095] cursor-pointer">
                      <input
                        type="checkbox"
                        value="realtime"
                        v-model="alertTranscriptionTypes"
                        class="rounded bg-[#13151A] border-[#2D3342] text-[#F59E0B] focus:ring-[#F59E0B]/30"
                      />
                      {{ t('settings.alerts.types_realtime') }}
                    </label>
                    <label class="inline-flex items-center gap-2 text-xs text-[#909095] cursor-pointer">
                      <input
                        type="checkbox"
                        value="file"
                        v-model="alertTranscriptionTypes"
                        class="rounded bg-[#13151A] border-[#2D3342] text-[#F59E0B] focus:ring-[#F59E0B]/30"
                      />
                      {{ t('settings.alerts.types_file') }}
                    </label>
                  </div>
                </div>
              </div>
            </div>

            <!-- TAB: REDE & IDIOMA -->
            <div v-else-if="activeTab === 'network'" class="flex flex-col gap-4">
              <div class="bento-card p-4 flex flex-col gap-3">
                <span class="text-xs font-bold text-[#DDE2F6]">Conectividade &amp; Localização</span>

                <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div>
                    <label class="block text-[11px] text-[#909095] font-medium mb-1">{{ t('settings.host') }}</label>
                    <input
                      v-model="networkHost"
                      type="text"
                      class="bento-input w-full py-1.5 px-3 text-xs font-mono"
                    />
                  </div>

                  <div>
                    <label class="block text-[11px] text-[#909095] font-medium mb-1">{{ t('settings.port') }}</label>
                    <input
                      v-model="networkPort"
                      type="number"
                      class="bento-input w-full py-1.5 px-3 text-xs font-mono"
                    />
                  </div>

                  <div>
                    <label class="block text-[11px] text-[#909095] font-medium mb-1">{{ t('settings.language') }}</label>
                    <select
                      v-model="appLanguage"
                      class="bento-input w-full px-3 py-1.5 text-xs bg-[#13151A]"
                    >
                      <option value="pt">Português (BR)</option>
                      <option value="en">English (US)</option>
                    </select>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Modal Footer Actions -->
        <div class="flex items-center justify-between px-6 py-3.5 border-t border-[#2D3342] bg-[#1A1D24]/80 flex-shrink-0">
          <div class="flex items-center gap-2">
            <span v-if="saved" class="text-xs text-[#10B981] font-semibold animate-pulse flex items-center gap-1">
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
              </svg>
              {{ t('settings.save_success') }}
            </span>
          </div>

          <div class="flex items-center gap-2">
            <button @click="close" class="bento-btn py-1.5 px-4 text-xs text-[#909095] hover:text-[#DDE2F6]">
              Cancelar
            </button>
            <button
              @click="save"
              class="bento-btn-primary py-1.5 px-4 text-xs font-semibold"
            >
              {{ t('prompt.save') }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue';
import { t } from '../../i18n';
import AgentsSettingsTab from './AgentsSettingsTab.vue';

const props = defineProps<{
  visible: boolean;
  initialTab?: 'prompt' | 'providers' | 'agents' | 'storage' | 'tray' | 'network';
}>();
const emit = defineEmits<{ close: [] }>();

// Tab Control
const activeTab = ref<'prompt' | 'providers' | 'agents' | 'storage' | 'tray' | 'network'>('prompt');

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
const minimaxKey = ref('');
const minimaxBaseUrl = ref('https://api.minimax.io/v1');
const minimaxModel = ref('MiniMax-Text-01');
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
const showMinimaxKey = ref(false);

// Models Lists
const loadingModels = ref(false);
const geminiModelsList = ref<string[]>([]);
const groqModelsList = ref<string[]>([]);
const minimaxModelsList = ref<string[]>([]);

const saved = ref(false);
const API = 'http://localhost:18763';

function insertPromptVariable(variableText: string) {
  textoPrompt.value += (textoPrompt.value ? '\n' : '') + variableText;
}

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
    minimaxKey.value = data.minimax_key_masked || '';
    minimaxBaseUrl.value = data.minimax_base_url || 'https://api.minimax.io/v1';
    minimaxModel.value = data.minimax_model || 'MiniMax-Text-01';
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
        minimax_key: minimaxKey.value,
        minimax_base_url: minimaxBaseUrl.value,
      }),
    });
    if (res.ok) {
      const data = await res.json();
      geminiModelsList.value = data.gemini_models || [];
      groqModelsList.value = data.groq_models || [];
      minimaxModelsList.value = data.minimax_models || [];

      // Append saved model if not returned by list
      if (geminiModel.value && !geminiModelsList.value.includes(geminiModel.value)) {
        geminiModelsList.value.unshift(geminiModel.value);
      }
      if (groqModel.value && !groqModelsList.value.includes(groqModel.value)) {
        groqModelsList.value.unshift(groqModel.value);
      }
      if (minimaxModel.value && !minimaxModelsList.value.includes(minimaxModel.value)) {
        minimaxModelsList.value.unshift(minimaxModel.value);
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
        minimax_key: minimaxKey.value,
        minimax_base_url: minimaxBaseUrl.value,
        minimax_model: minimaxModel.value,
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
      }, 1200);
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
    activeTab.value = props.initialTab || 'prompt';
    showGeminiKey.value = false;
    showGroqKey.value = false;
    loadPrompt();
    loadSettings();
  }
});
</script>
