<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 select-none font-inter"
      @click.self="close"
    >
      <div class="bg-[#16181F] border border-[#2D3342] rounded-xl w-full max-w-md p-5 shadow-2xl animate-slide-in flex flex-col gap-4">
        <!-- Header -->
        <div class="flex items-center justify-between border-b border-[#2D3342] pb-3">
          <div class="flex items-center gap-2">
            <div class="w-7 h-7 rounded-lg bg-[#222733] border border-[#3F444E] flex items-center justify-center text-[#F59E0B]">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.75" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
              </svg>
            </div>
            <div>
              <h3 class="text-xs font-bold text-[#DDE2F6]">Identificar Interlocutor</h3>
              <p class="text-[10px] text-[#909095]">Renomear todas as falas deste participante</p>
            </div>
          </div>
          <button @click="close" class="text-[#909095] hover:text-[#DDE2F6] p-1 rounded hover:bg-[#222733] transition-colors">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <!-- Form fields -->
        <div class="flex flex-col gap-3">
          <div>
            <label class="block text-[11px] text-[#909095] font-medium mb-1">Tag Atual no Documento</label>
            <input
              :value="currentTag"
              type="text"
              readonly
              class="bento-input w-full py-1.5 px-3 text-xs font-mono text-[#909095] bg-[#13151A] cursor-not-allowed"
            />
          </div>

          <div>
            <label class="block text-[11px] text-[#909095] font-medium mb-1">Novo Nome do Interlocutor</label>
            <input
              ref="nameInputEl"
              v-model="newName"
              type="text"
              placeholder="Ex: Dr. Roberto, Entrevistador, etc."
              class="bento-input w-full py-1.5 px-3 text-xs"
              @keydown.enter.prevent="applyRename"
            />
          </div>

          <div v-if="occurrenceCount > 0" class="text-[10px] text-[#F59E0B] bg-[#F59E0B]/10 border border-[#F59E0B]/20 rounded p-2 flex items-center gap-1.5">
            <svg class="w-3.5 h-3.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span>Serão renomeadas <strong>{{ occurrenceCount }} ocorrências</strong> desta tag em toda a transcrição.</span>
          </div>
        </div>

        <!-- Actions -->
        <div class="flex items-center justify-end gap-2 border-t border-[#2D3342] pt-3">
          <button @click="close" class="bento-btn px-3 py-1.5 text-xs text-[#909095] hover:text-[#DDE2F6]">
            Cancelar
          </button>
          <button
            @click="applyRename"
            :disabled="!newName.trim()"
            class="bento-btn-primary px-3 py-1.5 text-xs font-semibold disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Renomear em Massa
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue';

const props = defineProps<{
  visible: boolean;
  currentTag: string;
  occurrenceCount: number;
}>();

const emit = defineEmits<{
  close: [];
  rename: [oldTag: string, newTag: string];
}>();

const newName = ref('');
const nameInputEl = ref<HTMLInputElement | null>(null);

function applyRename() {
  const cleanName = newName.value.trim();
  if (!cleanName) return;
  const formattedNewTag = cleanName.startsWith('@') ? (cleanName.endsWith(':') ? cleanName : `${cleanName}:`) : `@${cleanName}:`;
  emit('rename', props.currentTag, formattedNewTag);
  newName.value = '';
  close();
}

function close() {
  emit('close');
}

watch(
  () => props.visible,
  async (v) => {
    if (v) {
      newName.value = '';
      await nextTick();
      nameInputEl.value?.focus();
    }
  }
);
</script>
