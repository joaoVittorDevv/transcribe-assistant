<template>
  <BubbleMenu
    v-if="editor"
    :editor="editor"
    class="editor-bubble-menu flex items-center gap-1 p-1 bg-[#1A1D24] border border-[#2D3342] rounded-md shadow-2xl z-40 select-none font-inter animate-slide-in"
  >
    <!-- Text Formatting Actions -->
    <button
      type="button"
      @click="editor.chain().focus().toggleBold().run()"
      :class="[
        'w-6 h-6 flex items-center justify-center rounded text-xs transition-colors',
        editor.isActive('bold') ? 'text-[#F59E0B] bg-[#F59E0B]/15' : 'text-[#909095] hover:text-[#DDE2F6] hover:bg-[#222733]'
      ]"
      title="Negrito"
    >
      <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor">
        <path d="M6 4h8a4 4 0 014 4 4 4 0 01-4 4H6z"/><path d="M6 12h9a4 4 0 014 4 4 4 0 01-4 4H6z"/>
      </svg>
    </button>

    <button
      type="button"
      @click="editor.chain().focus().toggleItalic().run()"
      :class="[
        'w-6 h-6 flex items-center justify-center rounded text-xs transition-colors',
        editor.isActive('italic') ? 'text-[#F59E0B] bg-[#F59E0B]/15' : 'text-[#909095] hover:text-[#DDE2F6] hover:bg-[#222733]'
      ]"
      title="Itálico"
    >
      <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor">
        <path d="M10 4l2 0-4 16-2 0zM8 4l6 0M6 20l6 0"/>
      </svg>
    </button>

    <button
      type="button"
      @click="editor.chain().focus().toggleStrike().run()"
      :class="[
        'w-6 h-6 flex items-center justify-center rounded text-xs transition-colors',
        editor.isActive('strike') ? 'text-[#F59E0B] bg-[#F59E0B]/15' : 'text-[#909095] hover:text-[#DDE2F6] hover:bg-[#222733]'
      ]"
      title="Tachado"
    >
      <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M5 12h14M12 5l0 14"/>
      </svg>
    </button>

    <button
      type="button"
      @click="editor.chain().focus().toggleCode().run()"
      :class="[
        'w-6 h-6 flex items-center justify-center rounded text-xs transition-colors',
        editor.isActive('code') ? 'text-[#F59E0B] bg-[#F59E0B]/15' : 'text-[#909095] hover:text-[#DDE2F6] hover:bg-[#222733]'
      ]"
      title="Código Inline"
    >
      <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75">
        <path stroke-linecap="round" stroke-linejoin="round" d="M17.25 6.75L22.5 12l-5.25 5.25m-10.5 0L1.5 12l5.25-5.25m7.5-3l-4.5 16.5" />
      </svg>
    </button>

    <div class="w-px h-4 bg-[#2D3342] mx-0.5"></div>

    <!-- Quick Speaker Prefix Buttons -->
    <button
      type="button"
      @click="prependSpeakerTag('@Usuario: ')"
      class="px-1.5 py-0.5 rounded text-[10px] font-mono font-medium text-[#3B82F6] hover:bg-[#3B82F6]/15 transition-colors border border-[#3B82F6]/30"
      title="Prefixar seleção com tag de @Usuario"
    >
      + @Usuario
    </button>

    <button
      type="button"
      @click="prependSpeakerTag('@Interlocutor 1: ')"
      class="px-1.5 py-0.5 rounded text-[10px] font-mono font-medium text-[#F59E0B] hover:bg-[#F59E0B]/15 transition-colors border border-[#F59E0B]/30"
      title="Prefixar seleção com tag de @Interlocutor"
    >
      + @Interlocutor
    </button>
  </BubbleMenu>
</template>

<script setup lang="ts">
import { BubbleMenu } from '@tiptap/vue-3/menus';
import type { Editor } from '@tiptap/vue-3';

const props = defineProps<{
  editor: Editor | null | undefined;
}>();

function prependSpeakerTag(tag: string) {
  if (!props.editor) return;
  const { from, to } = props.editor.state.selection;
  const selectedText = props.editor.state.doc.textBetween(from, to, ' ');
  props.editor.chain().focus().deleteRange({ from, to }).insertContentAt(from, `${tag}${selectedText}`).run();
}
</script>
