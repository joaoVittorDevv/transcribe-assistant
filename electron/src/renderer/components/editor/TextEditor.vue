<template>
  <div class="editor-wrapper flex flex-col flex-1 min-h-0">
    <EditorToolbar :activeFormats="activeFormats" @format="handleFormat" />
    <FindReplaceBar
      ref="findBarRef"
      :visible="findBarVisible"
      :matchCount="matchCount"
      :activeMatchIndex="activeMatchIndex"
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
      <EditorContent :editor="editor" class="h-full" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted, watch, nextTick } from 'vue';
import { useEditor, EditorContent } from '@tiptap/vue-3';
import StarterKit from '@tiptap/starter-kit';
import { Markdown } from '@tiptap/markdown';
import SearchAndReplace from '@sereneinserenade/tiptap-search-and-replace';
import EditorToolbar from './EditorToolbar.vue';
import FindReplaceBar from './FindReplaceBar.vue';
import { useTabs } from '../../composables/useTabs';
import { useEditor as useEditorComposable } from '../../composables/useEditor';
import { useStreamingTranscription } from '../../composables/useStreamingTranscription';
import type { ElectronAPI } from '../../types/global';

const findBarRef = ref<InstanceType<typeof FindReplaceBar> | null>(null);

const { activeTabId, getActiveTab, updateContent } = useTabs();
const { registerEditor } = useEditorComposable();
const api = window.electronAPI as ElectronAPI;

const activeFormats = reactive<Set<string>>(new Set());

let transcriptionInsertIndex: number | null = null;
// Start of the text this transcription session has written, so the final
// authoritative snapshot can replace it without duplicating or eating user text.
let transcriptionRangeStart: number | null = null;
// Tracks insertion point during transcription streaming.
// Captured as a ProseMirror position index.

// ------------------------------------------------------------------
// Find & Replace state
// ------------------------------------------------------------------
const findBarVisible = ref(false);
const matchCount = ref(0);
const activeMatchIndex = ref(0);

function updateSearchState() {
  if (!editor.value) return;
  const storage = (editor.value.storage as any).searchAndReplace;
  if (storage) {
    matchCount.value = storage.results?.length || 0;
    activeMatchIndex.value = storage.resultIndex ?? 0;
  }
}

// Schedule a delayed search state update to allow ProseMirror
// decoration plugin to finish processing before reading results.
function scheduleSearchStateUpdate() {
  setTimeout(() => updateSearchState(), 50);
}

function onFind(searchText: string) {
  if (!editor.value) return;
  (editor.value.commands as any).setSearchTerm(searchText);
  scheduleSearchStateUpdate();
}

function navigateMatch(direction: 'next' | 'prev') {
  if (!editor.value) return;
  if (direction === 'next') {
    (editor.value.commands as any).findNext();
  } else {
    (editor.value.commands as any).findPrev();
  }
  scheduleSearchStateUpdate();
}

function replaceOne() {
  if (!editor.value) return;
  const replaceText = findBarRef.value?.replaceText || '';
  (editor.value.commands as any).setReplaceTerm(replaceText);
  (editor.value.commands as any).replace();
  scheduleSearchStateUpdate();
}

function replaceAllMatches() {
  if (!editor.value) return;
  const replaceText = findBarRef.value?.replaceText || '';
  (editor.value.commands as any).setReplaceTerm(replaceText);
  (editor.value.commands as any).replaceAll();
  scheduleSearchStateUpdate();
}

function closeFindBar() {
  if (editor.value) {
    (editor.value.commands as any).setSearchTerm('');
  }
  matchCount.value = 0;
  activeMatchIndex.value = 0;
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
    if (target.closest('.find-replace-bar')) return;
    e.preventDefault();
    closeFindBar();
  }
}

// ------------------------------------------------------------------
// Format state tracking
// ------------------------------------------------------------------
function computeActiveFormats() {
  activeFormats.clear();
  const ed = editor.value;
  if (!ed) return;

  if (ed.isActive('bold')) activeFormats.add('bold');
  if (ed.isActive('italic')) activeFormats.add('italic');
  if (ed.isActive('strike')) activeFormats.add('strike');
  if (ed.isActive('code')) activeFormats.add('code');
  if (ed.isActive('codeBlock')) activeFormats.add('codeBlock');

  // Header levels
  if (ed.isActive('heading', { level: 1 })) activeFormats.add('header:1');
  if (ed.isActive('heading', { level: 2 })) activeFormats.add('header:2');
  if (ed.isActive('heading', { level: 3 })) activeFormats.add('header:3');

  // List types
  if (ed.isActive('bulletList')) activeFormats.add('list:bullet');
  if (ed.isActive('orderedList')) activeFormats.add('list:ordered');
}

// ------------------------------------------------------------------
// TipTap Editor instance
// ------------------------------------------------------------------
const initialTab = getActiveTab();
const editor = useEditor({
  content: initialTab?.content || '',
  extensions: [
    StarterKit.configure({
      codeBlock: {
        HTMLAttributes: {
          class: 'premium-code-block bg-neutral-955/60 border border-white/10 rounded-xl p-4 font-mono text-sm text-gray-200 overflow-x-auto my-3 select-text',
        },
      },
    }),
    Markdown,
    SearchAndReplace.configure({
      searchResultClass: 'search-result bg-yellow-500/25 text-yellow-200 border-b-2 border-yellow-500 rounded-sm px-0.5',
    }),
  ],
  onUpdate: ({ editor }) => {
    const md = (editor as any)?.getMarkdown?.() ?? (editor.storage.markdown as any)?.getMarkdown?.() ?? editor.state.doc.textContent;
    updateContent(activeTabId.value, md);
    updateSearchState();
  },
  onSelectionUpdate: () => {
    computeActiveFormats();
  },
});

async function insertTextWithAck(text: string, tabId?: string): Promise<void> {
  const ed = editor.value;
  if (!ed) return;

  if (tabId && tabId !== activeTabId.value) {
    const { tabs } = useTabs();
    const targetTab = tabs.find(t => t.id === tabId);
    if (targetTab) {
      updateContent(tabId, targetTab.content + text);
    }
    return;
  }

  if (transcriptionInsertIndex === null) {
    const { selection } = ed.state;
    transcriptionInsertIndex = selection ? selection.anchor : ed.state.doc.content.size;
    transcriptionRangeStart = transcriptionInsertIndex;
  }

  const maxPos = ed.state.doc.content.size;
  if (transcriptionInsertIndex > maxPos) {
    transcriptionInsertIndex = maxPos;
  }

  const oldSize = ed.state.doc.content.size;

  // BUG FIX: Em vez de usar tr.insert e ed.schema.text (que remove quebras
  // de linha e ignora formatação), usamos insertContentAt do TipTap. 
  // Ele entende Markdown e HTML e insere blocos corretos (parágrafos/br).
  ed.commands.insertContentAt(transcriptionInsertIndex, text);
  
  const newSize = ed.state.doc.content.size;

  // Avança o índice exatamente pela quantidade de conteúdo gerado,
  // garantindo precisão milimétrica mesmo se o Tiptap criou novos nós <p>.
  transcriptionInsertIndex += (newSize - oldSize);

  // Não precisamos chamar ed.view.dispatch() pois o ed.commands já o faz!

  ed.commands.setTextSelection(transcriptionInsertIndex);
  ed.commands.scrollIntoView();

  // Wait for DOM update
  await nextTick();
}

function resetInsertionPoint() {
  transcriptionInsertIndex = null;
  transcriptionRangeStart = null;
}

/**
 * Replace only the text written by this transcription session with the server's
 * persisted snapshot. Text the user typed outside that range is never touched.
 */
async function replaceTranscriptionText(text: string): Promise<void> {
  const ed = editor.value;
  if (!ed) return;

  if (transcriptionRangeStart === null || transcriptionInsertIndex === null) {
    await insertTextWithAck(text);
    return;
  }

  const from = Math.min(transcriptionRangeStart, ed.state.doc.content.size);
  const to = Math.min(transcriptionInsertIndex, ed.state.doc.content.size);
  const oldSize = ed.state.doc.content.size;

  ed.chain().deleteRange({ from, to }).insertContentAt(from, text).run();

  transcriptionInsertIndex = from + (ed.state.doc.content.size - oldSize) + (to - from);
  ed.commands.setTextSelection(transcriptionInsertIndex);
  ed.commands.scrollIntoView();
  await nextTick();
}

onMounted(() => {
  // Register editor API (clear + markdown export + undo + ack-based insert)
  registerEditor({ clearEditor, getMarkdown, undo: undoEditor, insertTextWithAck, resetInsertionPoint, replaceTranscriptionText });

  // Keyboard shortcut listener
  document.addEventListener('keydown', onEditorKeydown);

  // Streaming ASR listener integration
  const { onInterim, onFinal } = useStreamingTranscription();
  let streamingStartIndex: number | null = null;

  onInterim((text: string) => {
    const ed = editor.value;
    if (!ed) return;

    if (streamingStartIndex === null) {
      if (!text) return;
      const { selection } = ed.state;
      streamingStartIndex = selection ? selection.anchor : ed.state.doc.content.size;
    }

    const maxPos = ed.state.doc.content.size;
    if (!text) {
      // Clear provisional text and reset
      ed.chain().deleteRange({ from: streamingStartIndex, to: maxPos }).run();
      streamingStartIndex = null;
      return;
    }

    ed.chain()
      .deleteRange({ from: streamingStartIndex, to: maxPos })
      .insertContentAt(streamingStartIndex, text)
      .setTextSelection({ from: streamingStartIndex, to: streamingStartIndex + text.length })
      .setItalic() // Apply italic formatting for provisional text visual styling
      .setTextSelection(streamingStartIndex + text.length)
      .scrollIntoView()
      .run();
  });

  onFinal((text: string) => {
    const ed = editor.value;
    if (!ed) return;

    if (streamingStartIndex !== null) {
      const maxPos = ed.state.doc.content.size;
      ed.chain()
        .deleteRange({ from: streamingStartIndex, to: maxPos })
        .insertContentAt(streamingStartIndex, text) // Insert consolidated text without formatting
        .setTextSelection(streamingStartIndex + text.length)
        .scrollIntoView()
        .run();

      transcriptionInsertIndex = streamingStartIndex + text.length;
      streamingStartIndex = null;
    } else {
      insertTextWithAck(text);
    }
  });
});

onUnmounted(() => {
  document.removeEventListener('keydown', onEditorKeydown);
});

// Reset insertion tracking on tab switch
watch(activeTabId, (newId, oldId) => {
  if (newId === oldId) return;
  transcriptionInsertIndex = null;
});

// Sync when tab content is updated in-place (e.g., Reset/Clear button)
watch(
  () => getActiveTab()?.content,
  (newMarkdown) => {
    const ed = editor.value;
    if (!ed) return;
    const currentMarkdown = (ed as any)?.getMarkdown?.() ?? (ed.storage.markdown as any)?.getMarkdown?.() ?? ed.state.doc.textContent;
    if (newMarkdown !== undefined && currentMarkdown !== newMarkdown) {
      ed.commands.setContent(newMarkdown, { emitUpdate: false } as any);
    }
  }
);

function handleFormat(type: string, value?: string | boolean | number) {
  const ed = editor.value;
  if (!ed) return;
  
  const chain = ed.chain().focus();
  
  if (type === 'bold') {
    chain.toggleBold().run();
  } else if (type === 'italic') {
    chain.toggleItalic().run();
  } else if (type === 'strike') {
    chain.toggleStrike().run();
  } else if (type === 'code') {
    chain.toggleCode().run();
  } else if (type === 'codeBlock') {
    chain.toggleCodeBlock().run();
  } else if (type === 'header') {
    if (value === 1) chain.toggleHeading({ level: 1 }).run();
    else if (value === 2) chain.toggleHeading({ level: 2 }).run();
    else if (value === 3) chain.toggleHeading({ level: 3 }).run();
  } else if (type === 'list') {
    if (value === 'bullet') chain.toggleBulletList().run();
    else if (value === 'ordered') chain.toggleOrderedList().run();
  }
}

function clearEditor() {
  const ed = editor.value;
  if (!ed) return;
  // Clear tab store first to prevent watcher from restoring content
  updateContent(activeTabId.value, '');
  // Clear editor without emitting update (avoids sync loop)
  ed.commands.clearContent(false);
}

function undoEditor() {
  editor.value?.commands.undo();
}

function getMarkdown() {
  if (!editor.value) return '';
  // Access Markdown extension API with safe fallback
  const md = (editor.value as any)?.getMarkdown?.() ?? (editor.value.storage.markdown as any)?.getMarkdown?.() ?? editor.value.state.doc.textContent;
  return md;
}

defineExpose({ clearEditor, getMarkdown, undo: undoEditor, insertTextWithAck, resetInsertionPoint, replaceTranscriptionText });
</script>

<style>
.ProseMirror {
  height: 100%;
  padding: 20px;
  line-height: 1.7;
  outline: none;
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-size: 14px;
  color: #E0E0E0;
  overflow-y: auto;
}

/* Custom CSS to mimic blank/empty placeholder without extension */
.ProseMirror p:first-child:last-child:has(br:only-child)::before {
  content: 'Comece a gravar ou escreva aqui...';
  color: #6b7280;
  pointer-events: none;
  float: left;
  height: 0;
  font-style: normal;
}

/* Custom styling for provisional streaming text */
.ProseMirror em {
  color: #9CA3AF !important;
  font-style: italic !important;
}

/* Premium styling for raw blockquotes */
.ProseMirror blockquote {
  border-left: 3px solid rgba(59, 130, 246, 0.5);
  padding-left: 16px;
  margin-left: 0;
  margin-right: 0;
  color: #9CA3AF;
  font-style: italic;
}

/* Bullet list and ordered list premium styling */
.ProseMirror ul {
  list-style-type: disc;
  padding-left: 24px;
  margin: 8px 0;
}

.ProseMirror ol {
  list-style-type: decimal;
  padding-left: 24px;
  margin: 8px 0;
}

.ProseMirror li {
  margin: 4px 0;
}

/* Headings premium spacing */
.ProseMirror h1 {
  font-size: 1.8rem;
  font-weight: 700;
  margin-top: 16px;
  margin-bottom: 8px;
  color: #FFFFFF;
}

.ProseMirror h2 {
  font-size: 1.4rem;
  font-weight: 600;
  margin-top: 14px;
  margin-bottom: 8px;
  color: #F3F4F6;
}

.ProseMirror h3 {
  font-size: 1.15rem;
  font-weight: 600;
  margin-top: 12px;
  margin-bottom: 6px;
  color: #E5E7EB;
}

/* Inline code styles */
.ProseMirror code:not(pre code) {
  background-color: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 4px;
  padding: 2px 6px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.85em;
  color: #38bdf8;
}

/* Active Search Result styling */
.ProseMirror .search-result {
  transition: background-color 0.15s ease;
}

/* Active result styling (simulating focus) */
.ProseMirror .search-result-current {
  background-color: rgba(249, 115, 22, 0.4) !important;
  border-bottom: 2px solid #f97316 !important;
  color: #ffedd5 !important;
}
</style>
