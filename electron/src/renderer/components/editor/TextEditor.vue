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
import { ref, reactive, onMounted, onUnmounted, watch } from 'vue';
import { useEditor, EditorContent } from '@tiptap/vue-3';
import StarterKit from '@tiptap/starter-kit';
import { Markdown } from '@tiptap/markdown';
import SearchAndReplace from '@sereneinserenade/tiptap-search-and-replace';
import EditorToolbar from './EditorToolbar.vue';
import FindReplaceBar from './FindReplaceBar.vue';
import { useTabs } from '../../composables/useTabs';
import { useEditor as useEditorComposable } from '../../composables/useEditor';
import type { ElectronAPI } from '../../types/global';

const findBarRef = ref<InstanceType<typeof FindReplaceBar> | null>(null);

const { activeTabId, getActiveTab, updateContent } = useTabs();
const { registerEditor } = useEditorComposable();
const api = window.electronAPI as ElectronAPI;

const activeFormats = reactive<Set<string>>(new Set());

let cleanupInsertText: (() => void) | null = null;
let cleanupResetInsertion: (() => void) | null = null;
// Tracks insertion point during transcription streaming.
// Captured as a ProseMirror position index.
let transcriptionInsertIndex: number | null = null;

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
    const md = (editor.storage.markdown as any).getMarkdown();
    updateContent(activeTabId.value, md);
    updateSearchState();
  },
  onSelectionUpdate: () => {
    computeActiveFormats();
  },
});

onMounted(() => {
  // Listen for transcription text insertions at cursor.
  cleanupInsertText = api.onInsertText((payload: { text: string; tabId?: string }) => {
    const ed = editor.value;
    if (!ed) return;

    const { text, tabId } = payload;

    // If tabId is specified and doesn't match active tab, buffer into tab store
    if (tabId && tabId !== activeTabId.value) {
      const { tabs } = useTabs();
      const targetTab = tabs.find(t => t.id === tabId);
      if (targetTab) {
        // Content stores Markdown directly
        updateContent(tabId, targetTab.content + text);
      }
      return;
    }

    // Initialize insertion point from current cursor on first chunk
    if (transcriptionInsertIndex === null) {
      const { selection } = ed.state;
      // selection.anchor represents absolute ProseMirror offset
      transcriptionInsertIndex = selection ? selection.anchor : ed.state.doc.content.size;
    }

    // Safety clamp: if user deleted text during transcription, don't overflow
    const maxPos = ed.state.doc.content.size;
    if (transcriptionInsertIndex > maxPos) {
      transcriptionInsertIndex = maxPos;
    }

    // Insert raw text at the tracked position using chain API.
    // Using chain().insertContentAt() with a plain string ensures
    // ProseMirror treats it as unformatted text — no Markdown parsing.
    // This prevents `---` being interpreted as <hr>, `@` as formatting, etc.
    const tr = ed.state.tr;
    const textNode = ed.schema.text(text);
    tr.insert(transcriptionInsertIndex, textNode);
    ed.view.dispatch(tr);

    // Advance insertion index by text length (plain text = 1:1 char-to-position)
    transcriptionInsertIndex += text.length;

    // Move the visual selection (cursor) to the end of the newly inserted text
    ed.commands.setTextSelection(transcriptionInsertIndex);

    // Scroll to keep inserted text visible during streaming
    ed.commands.scrollIntoView();
  });

  // Reset insertion tracking when new transcription starts
  cleanupResetInsertion = api.onResetInsertionPoint(() => {
    transcriptionInsertIndex = null;
  });

  // Register editor API (clear + markdown export + undo)
  registerEditor({ clearEditor, getMarkdown, undo: undoEditor });

  // Keyboard shortcut listener
  document.addEventListener('keydown', onEditorKeydown);
});

onUnmounted(() => {
  document.removeEventListener('keydown', onEditorKeydown);
  cleanupInsertText?.();
  cleanupResetInsertion?.();
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
    const currentMarkdown = (ed.storage.markdown as any).getMarkdown();
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
  const md = editor.value.storage.markdown?.getMarkdown?.();
  return md ?? editor.value.state.doc.textContent;
}

defineExpose({ clearEditor, getMarkdown, undo: undoEditor });
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
