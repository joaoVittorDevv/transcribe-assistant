<template>
  <div class="flex items-center gap-2">
    <button @click="onCopy" class="glass-btn flex items-center gap-1.5 text-xs py-1.5 px-3">
      <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
        <path stroke-linecap="round" stroke-linejoin="round" d="M15.666 3.888A2.25 2.25 0 0013.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 01-.75.75H9a.75.75 0 01-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 01-2.25 2.25H6.75A2.25 2.25 0 014.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 011.927-.184" />
      </svg>
      {{ t('buttons.copy') }}
    </button>
    <!-- Import Audio -->
    <button @click="importAudio" class="glass-btn flex items-center gap-1.5 text-xs py-1.5 px-3">
      <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
        <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
      </svg>
      {{ t('buttons.import_audio') }}
    </button>
    <button class="glass-btn flex items-center gap-1.5 text-xs py-1.5 px-3">
      <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
      {{ t('buttons.history') }}
    </button>
  </div>
</template>

<script setup lang="ts">
import { t } from '../../i18n';
import { useTabs } from '../../composables/useTabs';
import { useClipboard } from '../../composables/useClipboard';

const { activeTabId, updateContent } = useTabs();
const { copyToClipboard } = useClipboard();

async function onCopy() {
  const tab = useTabs().getActiveTab();
  if (tab?.content) await copyToClipboard(tab.content);
}

async function importAudio() {
  const filePath = await window.electronAPI.openFilePicker(['mp3', 'wav']);
  if (!filePath) return;

  const arrayBuffer = await window.electronAPI.readFile(filePath);
  if (!arrayBuffer) return;

  const ext = filePath.split('.').pop()?.toLowerCase() ?? 'wav';
  const mimeType = ext === 'mp3' ? 'audio/mpeg' : 'audio/wav';
  const blob = new Blob([arrayBuffer], { type: mimeType });
  const form = new FormData();
  form.append('audio', blob, filePath.split('/').pop() ?? 'audio');

  const res = await fetch('http://localhost:18763/transcribe', {
    method: 'POST',
    body: form,
  });
  if (!res.body) return;

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let accumulated = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const text = line.slice(6).trim();
        if (text === '[DONE]') {
          updateContent(activeTabId.value, accumulated);
          return;
        }
        if (!text.startsWith('[ERROR]')) {
          accumulated += text;
        }
      }
    }
  }
  updateContent(activeTabId.value, accumulated);
}
</script>
