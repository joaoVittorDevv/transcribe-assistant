<template>
  <div class="editor-wrapper flex flex-col flex-1 min-h-0 relative font-inter">
    <!-- Top Formatting Toolbar -->
    <EditorToolbar :activeFormats="activeFormats" @format="handleFormat" />

    <!-- Find & Replace Bento Bar -->
    <FindReplaceBar
      ref="findBarRef"
      :visible="findBarVisible"
      :matchCount="matchCount"
      :activeMatchIndex="activeMatchIndex"
      :initialMode="findBarMode"
      @search="onFind"
      @next="navigateMatch('next')"
      @prev="navigateMatch('prev')"
      @replace="replaceOne"
      @replace-all="replaceAllMatches"
      @close="closeFindBar"
    />

    <!-- Editor Container (Bento Canvas with Document & Status Bar) -->
    <div
      class="flex-1 bg-[#16181F] border border-[#2D3342] rounded-lg overflow-hidden flex flex-col focus-within:border-[#3B82F6] focus-within:ring-1 focus-within:ring-[#3B82F6]/40 transition-all duration-150 shadow-inner relative"
    >
      <!-- Rewriting Live Feedback Banner & Expandable Reasoning Drawer (Bento Glassmorphic) -->
      <div
        v-if="rewriting"
        class="bg-[#1A1D24]/95 border-b border-[#3B82F6]/40 text-xs backdrop-blur-md flex-shrink-0 select-none z-10 transition-all duration-200"
      >
        <div class="flex items-center justify-between px-3.5 py-2">
          <div class="flex items-center gap-2.5">
            <div class="w-5 h-5 rounded-full bg-[#3B82F6]/20 border border-[#3B82F6]/40 flex items-center justify-center text-[#60A5FA]">
              <svg class="animate-spin h-3.5 w-3.5 text-[#60A5FA]" viewBox="0 0 24 24" fill="none">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
              </svg>
            </div>
            <div class="flex items-center gap-2">
              <span class="font-bold text-[#DDE2F6]">{{ activeAgent?.icon || '✨' }} {{ activeAgent?.name || 'Agente de IA' }}</span>
              <span class="text-[#60A5FA] font-medium">— {{ reasoningStage || 'Processando raciocínio e refinando texto...' }}</span>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <button
              v-if="reasoningText"
              type="button"
              @click="isReasoningExpanded = !isReasoningExpanded"
              class="px-2 py-0.5 rounded text-[10.5px] font-medium bg-[#222733] hover:bg-[#3B82F6]/20 text-[#60A5FA] border border-[#3B82F6]/40 transition-colors flex items-center gap-1 cursor-pointer"
            >
              <span>🧠 {{ isReasoningExpanded ? 'Ocultar Raciocínio' : 'Ver Linha de Raciocínio' }}</span>
              <span class="text-[9px]">{{ isReasoningExpanded ? '▲' : '▼' }}</span>
            </button>
            <span class="px-2 py-0.5 rounded text-[10px] font-mono bg-[#3B82F6]/20 text-[#60A5FA] border border-[#3B82F6]/30">
              🔒 Editor Bloqueado
            </span>
          </div>
        </div>

        <!-- Live Collapsible Reasoning Drawer -->
        <div
          v-if="isReasoningExpanded && reasoningText"
          class="px-4 py-2.5 bg-[#13151A]/95 border-t border-[#2D3342] text-[11px] font-mono max-h-36 overflow-y-auto leading-relaxed select-text animate-fade-in"
        >
          <div class="flex items-center gap-1.5 text-[10px] text-[#60A5FA] font-bold uppercase tracking-wider mb-1">
            <span class="inline-block w-1.5 h-1.5 rounded-full bg-[#60A5FA] animate-ping"></span>
            Linha de Pensamento da IA (Reasoning Stream):
          </div>
          <div class="text-[#DDE2F6] whitespace-pre-wrap">{{ reasoningText }}</div>
        </div>
      </div>

      <!-- Contextual Bubble Menu on Selection -->
      <EditorBubbleMenu :editor="editor" />

      <!-- ProseMirror Document Area -->
      <div class="flex-1 overflow-y-auto min-h-0">
        <EditorContent :editor="editor" class="h-full" />
      </div>

      <!-- Editor Bottom Status Bar (Word count, chars, reading time, speaker stats) -->
      <EditorStatusBar :editor="editor" />
    </div>

    <!-- Speaker Mass Rename Modal -->
    <SpeakerRenameModal
      :visible="renameModalVisible"
      :currentTag="renameTargetTag"
      :occurrenceCount="renameOccurrenceCount"
      @close="renameModalVisible = false"
      @rename="handleSpeakerRename"
    />
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
import EditorBubbleMenu from './EditorBubbleMenu.vue';
import EditorStatusBar from './EditorStatusBar.vue';
import SpeakerRenameModal from './SpeakerRenameModal.vue';
import { SpeakerHighlightExtension } from './SpeakerHighlightExtension';
import { useTabs } from '../../composables/useTabs';
import { useEditor as useEditorComposable } from '../../composables/useEditor';
import { useRewriteAgents } from '../../composables/useRewriteAgents';
import type { ElectronAPI } from '../../types/global';

const findBarRef = ref<InstanceType<typeof FindReplaceBar> | null>(null);

const { activeTabId, getActiveTab, updateContent } = useTabs();
const { registerEditor } = useEditorComposable();
const {
  rewriting,
  activeAgent,
  reasoningText,
  reasoningStage,
  isReasoningExpanded,
} = useRewriteAgents();
const api = window.electronAPI as ElectronAPI;

const activeFormats = reactive<Set<string>>(new Set());

// Watch rewriting state to toggle editor editable lock
watch(rewriting, (isRewriting) => {
  const ed = editor.value;
  if (!ed) return;
  ed.setEditable(!isRewriting);
});

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
const findBarMode = ref<'find' | 'replace'>('find');
const matchCount = ref(0);
const activeMatchIndex = ref(0);

// ------------------------------------------------------------------
// Speaker Rename Modal state
// ------------------------------------------------------------------
const renameModalVisible = ref(false);
const renameTargetTag = ref('');
const renameOccurrenceCount = ref(0);

function openSpeakerRename(speakerTag: string) {
  const ed = editor.value;
  if (!ed) return;
  renameTargetTag.value = speakerTag;
  const docText = ed.state.doc.textContent || '';
  const escaped = speakerTag.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const matches = docText.match(new RegExp(escaped, 'gi'));
  renameOccurrenceCount.value = matches ? matches.length : 1;
  renameModalVisible.value = true;
}

function handleSpeakerRename(oldTag: string, newTag: string) {
  const ed = editor.value;
  if (!ed) return;
  const currentMarkdown = (ed as any)?.getMarkdown?.() ?? (ed.storage.markdown as any)?.getMarkdown?.() ?? ed.state.doc.textContent;
  const escaped = oldTag.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const updatedMarkdown = currentMarkdown.replace(new RegExp(escaped, 'gi'), newTag);
  ed.commands.setContent(updatedMarkdown, { contentType: 'markdown' } as any);
  updateContent(activeTabId.value, updatedMarkdown);
}

function updateSearchState(shouldScroll = false) {
  if (!editor.value) return;
  const storage = (editor.value.storage as any).searchAndReplace;
  if (storage) {
    matchCount.value = storage.results?.length || 0;
    activeMatchIndex.value = storage.resultIndex ?? 0;
    if (shouldScroll && storage.results && storage.results[storage.resultIndex]) {
      const { from } = storage.results[storage.resultIndex];
      editor.value.commands.setTextSelection(from);
      editor.value.commands.scrollIntoView();
    }
  }
}

// Schedule a delayed search state update to allow ProseMirror
// decoration plugin to finish processing before reading results.
function scheduleSearchStateUpdate(shouldScroll = false) {
  setTimeout(() => updateSearchState(shouldScroll), 50);
}

function onFind(searchText: string, caseSensitive: boolean) {
  if (!editor.value) return;
  (editor.value.commands as any).setCaseSensitive(caseSensitive);
  (editor.value.commands as any).setSearchTerm(searchText);
  scheduleSearchStateUpdate(true);
}

function navigateMatch(direction: 'next' | 'prev') {
  if (!editor.value) return;
  if (direction === 'next') {
    (editor.value.commands as any).findNext();
  } else {
    (editor.value.commands as any).findPrev();
  }
  scheduleSearchStateUpdate(true);
}

function replaceOne() {
  if (!editor.value) return;
  const replaceText = findBarRef.value?.replaceText || '';
  (editor.value.commands as any).setReplaceTerm(replaceText);
  (editor.value.commands as any).replace();
  scheduleSearchStateUpdate(true);
}

function replaceAllMatches() {
  if (!editor.value) return;
  const replaceText = findBarRef.value?.replaceText || '';
  (editor.value.commands as any).setReplaceTerm(replaceText);
  (editor.value.commands as any).replaceAll();
  scheduleSearchStateUpdate(false);
}

function closeFindBar() {
  if (editor.value) {
    (editor.value.commands as any).setSearchTerm('');
  }
  matchCount.value = 0;
  activeMatchIndex.value = 0;
  findBarVisible.value = false;
}

function openFindBar(mode: 'find' | 'replace' = 'find') {
  findBarMode.value = mode;
  findBarVisible.value = true;
}

function onEditorKeydown(e: KeyboardEvent) {
  const target = e.target as HTMLElement;

  if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
    e.preventDefault();
    openFindBar('find');
    return;
  }

  if ((e.ctrlKey || e.metaKey) && e.key === 'h') {
    e.preventDefault();
    openFindBar('replace');
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
  contentType: 'markdown',
  extensions: [
    StarterKit.configure({
      codeBlock: {
        HTMLAttributes: {
          class: 'premium-code-block bg-neutral-955/60 border border-[#2D3342] rounded-lg p-3.5 font-mono text-xs text-[#DDE2F6] overflow-x-auto my-3 select-text',
        },
      },
    }),
    Markdown.configure({
      markedOptions: {
        breaks: true,
        gfm: true,
      },
    }),
    SearchAndReplace.configure({
      searchResultClass: 'search-result bg-yellow-500/25 text-yellow-200 border-b-2 border-yellow-500 rounded-sm px-0.5',
    }),
    SpeakerHighlightExtension.configure({
      onSpeakerClick: (speakerTag: string) => {
        openSpeakerRename(speakerTag);
      },
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
  ed.commands.insertContentAt(transcriptionInsertIndex, text, { contentType: 'markdown' } as any);
  
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

  ed.chain().deleteRange({ from, to }).insertContentAt(from, text, { contentType: 'markdown' } as any).run();

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
});

onUnmounted(() => {
  document.removeEventListener('keydown', onEditorKeydown);
});

// Reset insertion tracking on tab switch
watch(activeTabId, (newId, oldId) => {
  if (newId === oldId) return;
  transcriptionInsertIndex = null;
});

// Sync when tab content is updated in-place (e.g., Reset/Clear button or Rewrite stream)
watch(
  () => getActiveTab()?.content,
  (newMarkdown) => {
    const ed = editor.value;
    if (!ed) return;
    const currentMarkdown = (ed as any)?.getMarkdown?.() ?? (ed.storage.markdown as any)?.getMarkdown?.() ?? ed.state.doc.textContent;
    if (newMarkdown !== undefined && currentMarkdown !== newMarkdown) {
      ed.commands.setContent(newMarkdown, { emitUpdate: false, contentType: 'markdown' } as any);
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
  padding: 16px 20px;
  line-height: 1.7;
  outline: none;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  font-size: 13.5px;
  color: #DDE2F6;
  overflow-y: auto;
}

/* Paragraph spacing */
.ProseMirror p {
  margin-top: 0;
  margin-bottom: 0.75rem;
  line-height: 1.7;
}

.ProseMirror p:last-child {
  margin-bottom: 0;
}

/* Custom CSS to mimic blank/empty placeholder without extension */
.ProseMirror p:first-child:last-child:has(br:only-child)::before {
  content: 'Comece a gravar ou escreva aqui...';
  color: #909095;
  opacity: 0.5;
  pointer-events: none;
  float: left;
  height: 0;
  font-style: normal;
}

/* Premium styling for raw blockquotes */
.ProseMirror blockquote {
  border-left: 3px solid #3B82F6;
  padding-left: 14px;
  margin-left: 0;
  margin-right: 0;
  color: #909095;
  font-style: italic;
  margin-bottom: 0.75rem;
}

/* Bullet list and ordered list premium styling */
.ProseMirror ul {
  list-style-type: disc;
  padding-left: 20px;
  margin: 8px 0 12px 0;
}

.ProseMirror ol {
  list-style-type: decimal;
  padding-left: 20px;
  margin: 8px 0 12px 0;
}

.ProseMirror li {
  margin: 4px 0;
  line-height: 1.6;
}

.ProseMirror li > p {
  margin-bottom: 0.25rem;
}

/* Headings premium spacing */
.ProseMirror h1 {
  font-size: 1.6rem;
  font-weight: 700;
  margin-top: 18px;
  margin-bottom: 8px;
  color: #FFFFFF;
  line-height: 1.3;
}

.ProseMirror h2 {
  font-size: 1.3rem;
  font-weight: 600;
  margin-top: 16px;
  margin-bottom: 8px;
  color: #F3F4F6;
  line-height: 1.35;
}

.ProseMirror h3 {
  font-size: 1.1rem;
  font-weight: 600;
  margin-top: 12px;
  margin-bottom: 6px;
  color: #E5E7EB;
  line-height: 1.4;
}

/* Horizontal rule divider */
.ProseMirror hr {
  border: none;
  border-top: 1px solid #2D3342;
  margin: 1.25rem 0;
}

/* Inline code styles */
.ProseMirror code:not(pre code) {
  background-color: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 4px;
  padding: 1px 5px;
  font-family: 'JetBrains Mono', monospace, Consolas;
  font-size: 0.85em;
  color: #60A5FA;
}

/* Search Result styling */
.ProseMirror .search-result {
  background-color: rgba(245, 158, 11, 0.25);
  border-bottom: 2px solid rgba(245, 158, 11, 0.6);
  color: #FDE68A;
  border-radius: 2px;
  padding: 0 2px;
  transition: background-color 0.15s ease;
}

.ProseMirror .search-result-current {
  background-color: rgba(245, 158, 11, 0.6) !important;
  border-bottom: 2px solid #F59E0B !important;
  color: #FFFFFF !important;
  box-shadow: 0 0 8px rgba(245, 158, 11, 0.5);
}
</style>
