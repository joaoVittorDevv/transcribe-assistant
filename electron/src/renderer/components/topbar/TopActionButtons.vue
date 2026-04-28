<template>
  <div class="flex items-center gap-2">
    <!-- Import Audio -->
    <button @click="importAudio" class="glass-btn flex items-center gap-1.5 text-xs py-1.5 px-3">
      <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
        <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
      </svg>
      {{ t('buttons.import_audio') }}
    </button>
    <!-- Settings (gear) -->
    <button @click="emit('open-settings')" class="glass-btn flex items-center gap-1.5 text-xs py-1.5 px-3" :title="t('buttons.settings')">
      <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
        <path stroke-linecap="round" stroke-linejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z" />
        <path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    </button>
  </div>
</template>

<script setup lang="ts">
import { t } from '../../i18n';
import { useTabs } from '../../composables/useTabs';
import { useDefaultPrompt } from '../../composables/useDefaultPrompt';

const emit = defineEmits<{
  'open-settings': [];
}>();

const { activeTabId, updateContent } = useTabs();
const { promptData } = useDefaultPrompt();

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
  form.append('prompt_text', promptData.value.texto_prompt);
  form.append('keywords', promptData.value.keywords.join(', '));

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
