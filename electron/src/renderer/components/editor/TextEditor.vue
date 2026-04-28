<template>
  <div class="editor-wrapper flex flex-col flex-1 min-h-0">
    <EditorToolbar :activeFormats="activeFormats" @format="handleFormat" />
    <div
      class="flex-1 glass-surface rounded-xl overflow-hidden focus-within:ring-2 focus-within:ring-accent-blue/50 transition-shadow duration-150"
    >
      <div ref="editorEl" class="quill-editor h-full"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted, watch } from 'vue';
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

const activeFormats = reactive<Set<string>>(new Set());

let cleanupInsertText: (() => void) | null = null;

function computeActiveFormats(range: { index: number; length: number } | null) {
  activeFormats.clear();
  if (!quill || !range) return;

  const formats = quill.getFormat(range);

  // Inline formats
  if (formats.bold) activeFormats.add('bold');
  if (formats.italic) activeFormats.add('italic');
  if (formats.strike) activeFormats.add('strike');
  if (formats.code) activeFormats.add('code');

  // Header levels
  if (formats.header) activeFormats.add(`header:${formats.header}`);

  // List types
  if (formats.list) activeFormats.add(`list:${formats.list}`);
}

// ------------------------------------------------------------------
// Quill Delta → Markdown converter
// ------------------------------------------------------------------

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type QuillAttrs = Record<string, any>;

interface InlineSegment {
  text: string;
  attrs: QuillAttrs;
}

interface MarkdownLine {
  segments: InlineSegment[];
  blockAttrs: QuillAttrs;
}

function quillToMarkdown(): string {
  if (!quill) return '';

  const delta = quill.getContents();
  if (!delta.ops || delta.ops.length === 0) return '';

  // Split flat ops into lines, tracking block attrs on \n
  const lines: MarkdownLine[] = [];
  let currentSegments: InlineSegment[] = [];
  let blockAttrs: QuillAttrs = {};

  for (const op of delta.ops) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const opAttrs: QuillAttrs = (op as any).attributes || {};
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const insert: string | object = (op as any).insert;

    if (typeof insert !== 'string') {
      // Skip embeds (images, etc.)
      currentSegments.push({ text: '[mídia]', attrs: {} });
      continue;
    }

    if (!insert.includes('\n')) {
      // Plain text — no line break
      currentSegments.push({ text: insert, attrs: opAttrs });
      continue;
    }

    // Contains \n — split and finalize lines
    const parts = insert.split('\n');
    for (let i = 0; i < parts.length; i++) {
      if (i < parts.length - 1) {
        // Not the last part: end of a line
        if (parts[i]) {
          currentSegments.push({ text: parts[i], attrs: opAttrs });
        }
        lines.push({ segments: [...currentSegments], blockAttrs: { ...blockAttrs } });
        currentSegments = [];
        // The \n carries block-level formatting
        blockAttrs = opAttrs;
      } else {
        // Last part: continues to next line (or is empty if insert ends with \n)
        if (parts[i]) {
          currentSegments.push({ text: parts[i], attrs: opAttrs });
        }
      }
    }
  }

  // Flush remaining (last line without trailing \n)
  if (currentSegments.length > 0) {
    lines.push({ segments: [...currentSegments], blockAttrs: { ...blockAttrs } });
  }

  // Build Markdown output
  const resultLines: string[] = [];
  let orderedCounter = 1;

  for (const line of lines) {
    const attrs = line.blockAttrs;

    // Reset ordered counter between non-ordered blocks
    if (attrs.list !== 'ordered') {
      orderedCounter = 1;
    }

    // Build inline markdown
    let inlineText = '';
    for (const seg of line.segments) {
      let text = seg.text;
      const a = seg.attrs;

      // Apply inline format markers (innermost first)
      if (a.code) text = '`' + text + '`';
      if (a.bold) text = '**' + text + '**';
      if (a.italic) text = '*' + text + '*';
      if (a.strike) text = '~~' + text + '~~';
      if (a.link) text = '[' + text + '](' + a.link + ')';

      inlineText += text;
    }

    // Empty lines
    if (!inlineText.trim()) {
      resultLines.push('');
      continue;
    }

    // Code block: use fenced block
    if (attrs['code-block']) {
      resultLines.push('```\n' + inlineText + '\n```');
      continue;
    }

    let prefix = '';
    let indent = '';

    // Indentation level
    if (attrs.indent) {
      indent = '  '.repeat(Number(attrs.indent));
    }

    // Block formatting
    if (attrs.header) {
      prefix = '#'.repeat(Number(attrs.header)) + ' ';
    } else if (attrs.list === 'bullet') {
      prefix = '- ';
    } else if (attrs.list === 'ordered') {
      prefix = String(orderedCounter) + '. ';
      orderedCounter++;
    }

    // Blockquote wraps everything
    if (attrs.blockquote) {
      prefix = '> ' + prefix;
    }

    resultLines.push(indent + prefix + inlineText);
  }

  return resultLines.join('\n').trim();
}

// ------------------------------------------------------------------

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

  // Track active formats for toolbar highlight
  quill.on('selection-change', (range: { index: number; length: number } | null) => {
    computeActiveFormats(range);
  });

  // Listen for transcription text insertions at cursor
  cleanupInsertText = api.onInsertText((text: string) => {
    if (!quill) return;
    const sel = quill.getSelection(true);
    quill.insertText(sel?.index ?? quill.getLength(), text);
  });

  // Register editor API (clear + markdown export)
  registerEditor({ clearEditor, getMarkdown: quillToMarkdown });
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

defineExpose({ clearEditor, getMarkdown: quillToMarkdown });
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
