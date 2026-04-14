<template>
  <div class="editor-wrapper flex flex-col flex-1 min-h-0">
    <EditorToolbar @format="handleFormat" />
    <div
      class="flex-1 glass-surface rounded-xl overflow-hidden focus-within:ring-2 focus-within:ring-accent-blue/50 transition-shadow duration-150"
    >
      <div ref="editorEl" class="quill-editor h-full"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue';
import Quill from 'quill';
import 'quill/dist/quill.snow.css';
import EditorToolbar from './EditorToolbar.vue';
import { useTabs } from '../../composables/useTabs';
import { useEditor } from '../../composables/useEditor';
import type { ElectronAPI } from '../../types/global';

const editorEl = ref<HTMLElement | null>(null);
let quill: Quill | null = null;

const { activeTabId, getActiveTab, updateContent } = useTabs();
const { registerEditor } = useEditor();
const api = window.electronAPI as ElectronAPI;

let cleanupInsertText: (() => void) | null = null;

onMounted(() => {
  if (!editorEl.value) return;

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  quill = new Quill(editorEl.value, {
    theme: false as any,
    modules: {
      toolbar: false,
    },
  });

  // Load current tab content
  const tab = getActiveTab();
  if (tab?.content) {
    quill.setText(tab.content);
  }

  quill.on('text-change', () => {
    if (!quill) return;
    updateContent(activeTabId.value, quill.getText());
  });

  // Listen for transcription text insertions at cursor
  cleanupInsertText = api.onInsertText((text: string) => {
    if (!quill) return;
    const sel = quill.getSelection(true);
    quill.insertText(sel?.index ?? quill.getLength(), text);
  });

  // Register for reset functionality
  registerEditor({ clearEditor });
});

onUnmounted(() => {
  quill = null;
  cleanupInsertText?.();
});

// Sync when active tab changes or when tab content is updated in-place
watch(activeTabId, () => {
  if (!quill) return;
  const tab = getActiveTab();
  const newText = tab?.content ?? '';
  if (quill.getText() !== newText + '\n') {
    quill.setText(newText);
  }
});

function handleFormat(type: string, value?: string | boolean | number) {
  if (!quill) return;
  const range = quill.getSelection(true);
  if (value !== undefined) {
    quill.format(type, value);
  } else {
    const current = quill.getFormat(range);
    quill.format(type, !current[type]);
  }
}

function clearEditor() {
  if (!quill) return;
  quill.setText('');
}

defineExpose({ clearEditor });
</script>

<style>
.quill-editor {
  height: 100%;
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-size: 14px;
  color: #E0E0E0;
}

.ql-container {
  height: 100%;
  border: none !important;
  font-family: 'Plus Jakarta Sans', sans-serif;
}

.ql-editor {
  height: 100%;
  padding: 16px;
  line-height: 1.7;
}

.ql-editor.ql-blank::before {
  color: #9ca3af;
  font-style: normal;
  content: 'Comece a gravar ou escreva aqui...';
}
</style>
