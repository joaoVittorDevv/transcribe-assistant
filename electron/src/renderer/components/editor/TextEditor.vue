<template>
  <div class="editor-wrapper flex flex-col flex-1 min-h-0">
    <EditorToolbar :activeFormats="activeFormats" @format="handleFormat" />
    <FindReplaceBar
      ref="findBarRef"
      :visible="findBarVisible"
      :matchCount="matches.length"
      :activeMatchIndex="activeMatchIdx"
      @search="onFind"
      @next="navigateMatch('next')"
      @prev="navigateMatch('prev')"
      @replace="replaceOne"
      @replace-all="replaceAllMatches"
      @close="closeFindBar"
    />
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
import FindReplaceBar from './FindReplaceBar.vue';
import { useTabs } from '../../composables/useTabs';
import { useEditor } from '../../composables/useEditor';
import type { ElectronAPI } from '../../types/global';

const editorEl = ref<HTMLElement | null>(null);
const findBarRef = ref<InstanceType<typeof FindReplaceBar> | null>(null);
let quill: Quill | null = null;

const { activeTabId, getActiveTab, updateContent } = useTabs();
const { registerEditor } = useEditor();
const api = window.electronAPI as ElectronAPI;

const activeFormats = reactive<Set<string>>(new Set());

let cleanupInsertText: (() => void) | null = null;
let cleanupResetInsertion: (() => void) | null = null;
// Tracks insertion point during transcription streaming.
// On first chunk, captured from current cursor. Advanced by each chunk.
// Reset to null when transcription ends or user switches tabs.
let transcriptionInsertIndex: number | null = null;

// ------------------------------------------------------------------
// Find & Replace state
// ------------------------------------------------------------------

interface Match {
  index: number;
  length: number;
}

const findBarVisible = ref(false);
const matches = ref<Match[]>([]);
const activeMatchIdx = ref(0);
let lastSearchText = '';

function findAllMatches(searchText: string): Match[] {
  if (!quill || !searchText) return [];
  const fullText = quill.getText();
  const searchLower = searchText.toLowerCase();
  const textLower = fullText.toLowerCase();
  const result: Match[] = [];
  let startIndex = 0;
  while ((startIndex = textLower.indexOf(searchLower, startIndex)) !== -1) {
    result.push({ index: startIndex, length: searchText.length });
    startIndex += searchText.length;
  }
  return result;
}

function applyHighlights(activeIdx: number) {
  if (!quill) return;
  for (let i = 0; i < matches.value.length; i++) {
    const m = matches.value[i];
    const color = i === activeIdx ? '#F97316' : '#FBBF24';
    quill.formatText(m.index, m.length, 'background', color);
  }
}

function clearHighlights() {
  if (!quill) return;
  for (const m of matches.value) {
    quill.formatText(m.index, m.length, 'background', false);
  }
}

function onFind(searchText: string) {
  clearHighlights();
  matches.value = findAllMatches(searchText);
  activeMatchIdx.value = 0;
  lastSearchText = searchText;

  if (matches.value.length > 0) {
    // Only highlight — do NOT move cursor or focus the editor
    applyHighlights(0);
  }
}

function navigateMatch(direction: 'next' | 'prev') {
  if (matches.value.length === 0) return;
  const prevIdx = activeMatchIdx.value;
  if (direction === 'next') {
    activeMatchIdx.value = (activeMatchIdx.value + 1) % matches.value.length;
  } else {
    activeMatchIdx.value =
      (activeMatchIdx.value - 1 + matches.value.length) % matches.value.length;
  }
  // Update highlight colors for previous and new active
  if (quill) {
    quill.formatText(
      matches.value[prevIdx].index,
      matches.value[prevIdx].length,
      'background',
      '#FBBF24',
    );
    quill.formatText(
      matches.value[activeMatchIdx.value].index,
      matches.value[activeMatchIdx.value].length,
      'background',
      '#F97316',
    );
  }
  const active = matches.value[activeMatchIdx.value];
  quill!.setSelection(active.index, active.length);
  quill!.scrollSelectionIntoView();
}

function replaceOne() {
  // replaceText is accessed via FindReplaceBar's exposed ref
  if (!quill || matches.value.length === 0) return;
  const replaceText = findBarRef.value?.replaceText;
  if (!replaceText) return;

  const active = matches.value[activeMatchIdx.value];
  quill.deleteText(active.index, active.length);
  quill.insertText(active.index, replaceText);
  // Re-search after replace
  onFind(lastSearchText);
}

function replaceAllMatches() {
  if (!quill || matches.value.length === 0) return;
  const replaceText = findBarRef.value?.replaceText;
  if (!replaceText) return;

  // Replace from end to start to preserve indices
  const sorted = [...matches.value].sort((a, b) => b.index - a.index);
  for (const m of sorted) {
    quill.deleteText(m.index, m.length);
    quill.insertText(m.index, replaceText);
  }
  onFind(lastSearchText);
}

function closeFindBar() {
  clearHighlights();
  matches.value = [];
  activeMatchIdx.value = 0;
  lastSearchText = '';
  findBarVisible.value = false;
}

function openFindBar() {
  findBarVisible.value = true;
}

function onEditorKeydown(e: KeyboardEvent) {
  const target = e.target as HTMLElement;

  if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
    e.preventDefault();
    openFindBar();
    return;
  }

  if (e.key === 'Escape' && findBarVisible.value) {
    // Only close if not typing in the find bar inputs
    if (target.closest('.find-replace-bar')) return;
    e.preventDefault();
    closeFindBar();
  }
}

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

  // Listen for transcription text insertions at cursor.
  // Tracks insertion point locally so chunk order is always preserved:
  // - Captures cursor position on first chunk
  // - Inserts at tracked index (NOT re-reading cursor each time)
  // - Advances index by chunk length
  // - Moves cursor to end of inserted text
  cleanupInsertText = api.onInsertText((payload: { text: string; tabId?: string }) => {
    if (!quill) return;

    const { text, tabId } = payload;

    // If tabId is specified and doesn't match active tab, buffer into tab store
    if (tabId && tabId !== activeTabId.value) {
      const { tabs } = useTabs();
      const targetTab = tabs.find(t => t.id === tabId);
      if (targetTab) {
        updateContent(tabId, targetTab.content + text);
      }
      return;
    }

    // Initialize insertion point from current cursor on first chunk
    if (transcriptionInsertIndex === null) {
      const sel = quill.getSelection();
      // Quill's getLength() includes trailing \n — valid range is 0..getLength()-1
      transcriptionInsertIndex = sel ? sel.index : Math.max(0, quill.getLength() - 1);
    }

    // Safety clamp: if user deleted text during transcription, don't overflow
    const maxIndex = Math.max(0, quill.getLength() - 1);
    if (transcriptionInsertIndex > maxIndex) {
      transcriptionInsertIndex = maxIndex;
    }

    // Insert at the tracked position (NOT the current cursor)
    quill.insertText(transcriptionInsertIndex, text, 'user');

    // Advance the insertion point by the length of text just inserted
    transcriptionInsertIndex += text.length;

    // Move cursor to end of inserted text so user sees streaming progress
    quill.setSelection(transcriptionInsertIndex, 0);
  });

  // Reset insertion tracking when new transcription starts
  cleanupResetInsertion = api.onResetInsertionPoint(() => {
    transcriptionInsertIndex = null;
  });

  // Register editor API (clear + markdown export + undo)
  registerEditor({ clearEditor, getMarkdown: quillToMarkdown, undo: undoEditor });

  // Ctrl+F / Escape find bar keyboard handler
  document.addEventListener('keydown', onEditorKeydown);
});

onUnmounted(() => {
  document.removeEventListener('keydown', onEditorKeydown);
  quill = null;
  cleanupInsertText?.();
  cleanupResetInsertion?.();
});

// Sync when active tab changes or when tab content is updated in-place
watch(activeTabId, () => {
  if (!quill) return;
  const tab = getActiveTab();
  const newText = tab?.content ?? '';
  // Reset insertion tracking on tab switch — insertion point is tab-specific
  transcriptionInsertIndex = null;
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
  // Use 'user' source so the operation is recorded in Quill's history stack,
  // enabling undo via Ctrl+Z or the programmatic undo() call.
  quill.setText('', 'user');
}

function undoEditor() {
  if (!quill) return;
  quill.history.undo();
}

defineExpose({ clearEditor, getMarkdown: quillToMarkdown, undo: undoEditor });
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
