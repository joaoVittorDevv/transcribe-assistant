<template>
  <div class="editor-status-bar flex items-center justify-between px-3 py-1 bg-[#16181F] border-t border-[#2D3342] text-[11px] text-[#909095] select-none flex-shrink-0 font-inter">
    <!-- Left: Word, Char & Reading time counts -->
    <div class="flex items-center gap-3">
      <div class="flex items-center gap-1">
        <span class="font-semibold text-[#DDE2F6] font-mono">{{ wordCount }}</span>
        <span>palavras</span>
      </div>
      <span class="text-[#2D3342]">•</span>
      <div class="flex items-center gap-1">
        <span class="font-semibold text-[#DDE2F6] font-mono">{{ charCount }}</span>
        <span>caracteres</span>
      </div>
      <span class="text-[#2D3342]">•</span>
      <div class="flex items-center gap-1">
        <svg class="w-3 h-3 text-[#909095]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <span>~{{ readingTime }} min de leitura</span>
      </div>
    </div>

    <!-- Right: Speaker counters & Save indicator -->
    <div class="flex items-center gap-3">
      <div v-if="userInterventions > 0 || guestInterventions > 0" class="flex items-center gap-2">
        <span v-if="userInterventions > 0" class="flex items-center gap-1 px-1.5 py-0.5 rounded bg-[#3B82F6]/10 text-[#60A5FA] border border-[#3B82F6]/20 font-mono text-[10px]">
          <span>👤</span> {{ userInterventions }}
        </span>
        <span v-if="guestInterventions > 0" class="flex items-center gap-1 px-1.5 py-0.5 rounded bg-[#F59E0B]/10 text-[#FBBF24] border border-[#F59E0B]/20 font-mono text-[10px]">
          <span>👥</span> {{ guestInterventions }}
        </span>
        <span class="text-[#2D3342]">•</span>
      </div>

      <div class="flex items-center gap-1 text-[#10B981]">
        <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
        </svg>
        <span class="font-medium text-[10px]">Sincronizado</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { Editor } from '@tiptap/vue-3';

const props = defineProps<{
  editor: Editor | null | undefined;
}>();

const textContent = computed(() => {
  if (!props.editor) return '';
  return props.editor.state.doc.textContent || '';
});

const wordCount = computed(() => {
  const text = textContent.value.trim();
  if (!text) return 0;
  return text.split(/\s+/).filter(Boolean).length;
});

const charCount = computed(() => {
  return textContent.value.length;
});

const readingTime = computed(() => {
  const words = wordCount.value;
  if (words === 0) return 0;
  return Math.max(1, Math.ceil(words / 200));
});

const userInterventions = computed(() => {
  const text = textContent.value;
  if (!text) return 0;
  const matches = text.match(/@(Usuario|User):/gi);
  return matches ? matches.length : 0;
});

const guestInterventions = computed(() => {
  const text = textContent.value;
  if (!text) return 0;
  const matches = text.match(/@(Interlocutor|Speaker|\w+)\s*(?:\d+)?:/gi);
  if (!matches) return 0;
  const guestMatches = matches.filter(m => !m.toLowerCase().startsWith('@usuario:') && !m.toLowerCase().startsWith('@user:'));
  return guestMatches.length;
});
</script>
