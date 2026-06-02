import re
from pathlib import Path

content = Path("electron/src/renderer/composables/useTranscriptionState.ts").read_text()

# Add imports
new_imports = """import { ref, computed, onUnmounted, watch } from 'vue';
import { useTabs } from './useTabs';
import { useDefaultPrompt } from './useDefaultPrompt';
import { useProvider } from './useProvider';
import { useTranscriptionProgress, PROGRESS_STEPS, type ProgressPhase } from './useTranscriptionProgress';
import type { ElectronAPI } from '../types/global';
import { useSocket } from './useSocket';
import { useEditor } from './useEditor';
"""
content = re.sub(r'import.*?\n(?:import.*?\n)*', new_imports, content, count=1)

# Remove consumeSSEStream function completely
start_sse = content.find("// Shared SSE stream consumer")
end_sse = content.find("export function useTranscriptionState()")
if start_sse != -1 and end_sse != -1:
    content = content[:start_sse] + content[end_sse:]

# Replace the inner parts of useTranscriptionState
old_transcribeDual = """  // NOVO: Transcrição dual — envia dois arquivos separadamente
  async function transcribeDual(paths: { mic: string | null; sys: string | null }) {"""

new_transcribeDual = """  // Socket.IO event listeners setup (run once)
  let socketListenersInitialized = false;

  function initSocketListeners() {
    if (socketListenersInitialized) return;
    const { socket } = useSocket();
    const { insertTextWithAck } = useEditor();
    const { setPhase, reset: resetProgress } = useTranscriptionProgress();

    if (!socket.value) return;

    socket.value.on('transcription:chunk', async (payload, callback) => {
      if (payload.sessionId !== sessionId.value) {
        callback({ status: 'ignored' });
        return;
      }
      try {
        const { activeTabId } = useTabs();
        await insertTextWithAck(payload.text, activeTabId.value);
        callback({ status: 'ok' });
      } catch (e) {
        console.error('[Socket.IO] Error inserting text:', e);
        // Do not ack or maybe ack with error to trigger retry? We'll ack to keep it flowing.
        callback({ status: 'error' });
      }
    });

    socket.value.on('transcription:status', (payload) => {
      if (payload.sessionId !== sessionId.value) return;
      const phase = payload.phase as ProgressPhase;
      const message = payload.message;
      if (phase === 'error') {
        setPhase('error', message || 'Erro na transcrição');
      } else {
        const knownPhases = new Set(PROGRESS_STEPS.map((s) => s.id));
        if (knownPhases.has(phase)) {
          setPhase(phase, message);
        } else if (phase === 'cancelled') {
           // handled in handleCancel
        }
      }
    });

    socket.value.on('transcription:error', (payload) => {
      if (payload.sessionId !== sessionId.value) return;
      setPhase('error', payload.message || 'Erro desconhecido');
      api.updateAudioState('error');
    });

    socket.value.on('transcription:done', (payload) => {
      if (payload.sessionId !== sessionId.value) return;
      setPhase('done');
      setTimeout(() => {
        resetProgress();
        state.value = 'IDLE';
        elapsedSeconds.value = 0;
        sessionId.value = null;
      }, 2000);
    });

    socketListenersInitialized = true;
  }

  // NOVO: Transcrição dual — envia dois arquivos separadamente
  async function transcribeDual(paths: { mic: string | null; sys: string | null }) {"""

content = content.replace(old_transcribeDual, new_transcribeDual)

# Inside transcribeDual:
old_dual_fetch = """      const response = await fetch(`http://localhost:18763/transcribe/dual`, {
        method: 'POST',
        body: formData,
        signal: abortController.signal,
      });

      // Capture session ID from response headers
      const sid = response.headers.get('X-Session-ID');
      if (sid) sessionId.value = sid;

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');

      await consumeSSEStream({
        reader,
        targetTabId,
        setPhase,
        resetProgress,
        logPrefix: 'dual',
        onDone: () => {
          // Clean up dual audio files on success
          if (micPath) api.deleteFile(micPath).catch(() => {});
          if (sysPath) api.deleteFile(sysPath).catch(() => {});
        },
      });

      if (!response.ok) {
        console.error('[transcription] dual HTTP error:', response.status, response.statusText);
        setPhase('error', `Erro HTTP ${response.status}: ${response.statusText}`);
        return;
      }
    } catch (err: any) {"""

new_dual_fetch = """      const { socket } = useSocket();
      initSocketListeners();
      
      if (socket.value) {
        formData.append('X-Socket-ID', socket.value.id || '');
      }

      const response = await fetch(`http://localhost:18763/transcribe/dual`, {
        method: 'POST',
        body: formData,
        signal: abortController.signal,
        headers: socket.value?.id ? { 'X-Socket-ID': socket.value.id } : {}
      });

      if (!response.ok) {
        console.error('[transcription] dual HTTP error:', response.status, response.statusText);
        setPhase('error', `Erro HTTP ${response.status}: ${response.statusText}`);
        return;
      }

      const resData = await response.json();
      sessionId.value = resData.sessionId;

      // Clean up files locally (server makes a copy)
      if (micPath) api.deleteFile(micPath).catch(() => {});
      if (sysPath) api.deleteFile(sysPath).catch(() => {});

    } catch (err: any) {"""

content = content.replace(old_dual_fetch, new_dual_fetch)


# Inside transcribeFile
old_single_fetch = """      const response = await fetch(`http://localhost:18763/transcribe`, {
        method: 'POST',
        body: formData,
        signal: abortController.signal,
      });

      // Capture session ID from response headers for server-side cancel
      const sid = response.headers.get('X-Session-ID');
      if (sid) sessionId.value = sid;

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');

      await consumeSSEStream({
        reader,
        targetTabId,
        setPhase,
        resetProgress,
        logPrefix: 'single',
        onDone: () => {
          // Clean up Vault file on successful transcription
          if (wavPath) {
            api.deleteFile(wavPath).catch(() => {});
          }
        },
      });

      if (!response.ok) {
        console.error('[transcription] HTTP error:', response.status, response.statusText);
        setPhase('error', `Erro HTTP ${response.status}: ${response.statusText}`);
        return;
      }
    } catch (err: any) {"""

new_single_fetch = """      const { socket } = useSocket();
      initSocketListeners();

      const response = await fetch(`http://localhost:18763/transcribe`, {
        method: 'POST',
        body: formData,
        signal: abortController.signal,
        headers: socket.value?.id ? { 'X-Socket-ID': socket.value.id } : {}
      });

      if (!response.ok) {
        console.error('[transcription] HTTP error:', response.status, response.statusText);
        setPhase('error', `Erro HTTP ${response.status}: ${response.statusText}`);
        return;
      }

      const resData = await response.json();
      sessionId.value = resData.sessionId;

      if (wavPath) {
        api.deleteFile(wavPath).catch(() => {});
      }

    } catch (err: any) {"""

content = content.replace(old_single_fetch, new_single_fetch)

# Inside handleCancel:
old_cancel = """    } else if (state.value === 'TRANSCRIBING') {
      // Cancel transcription: abort in-flight fetch + notify server
      abortController?.abort();
      if (sessionId.value) {
        fetch(`http://localhost:18763/transcribe/${sessionId.value}`, {
          method: 'DELETE',
        }).catch(() => {});
      }"""

new_cancel = """    } else if (state.value === 'TRANSCRIBING') {
      abortController?.abort();
      const { socket } = useSocket();
      if (sessionId.value && socket.value) {
        socket.value.emit('transcription:cancel', { sessionId: sessionId.value });
        // Also fire the HTTP DELETE just in case as fallback (idempotent)
        fetch(`http://localhost:18763/transcribe/${sessionId.value}`, {
          method: 'DELETE',
        }).catch(() => {});
      }"""
content = content.replace(old_cancel, new_cancel)

# Inside importAndTranscribe:
old_import_fetch = """      const response = await fetch('http://localhost:18763/transcribe', {
        method: 'POST',
        body: formData,
        signal: abortController.signal,
      });

      // Capture session ID from response headers
      const sid = response.headers.get('X-Session-ID');
      if (sid) sessionId.value = sid;

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');

      await consumeSSEStream({
        reader,
        targetTabId,
        setPhase,
        resetProgress,
        logPrefix: 'import',
      });

      if (!response.ok) {
        setPhase('error', `Erro HTTP ${response.status}: ${response.statusText}`);
        return;
      }
    } catch (err: any) {"""

new_import_fetch = """      const { socket } = useSocket();
      initSocketListeners();

      const response = await fetch('http://localhost:18763/transcribe', {
        method: 'POST',
        body: formData,
        signal: abortController.signal,
        headers: socket.value?.id ? { 'X-Socket-ID': socket.value.id } : {}
      });

      if (!response.ok) {
        setPhase('error', `Erro HTTP ${response.status}: ${response.statusText}`);
        return;
      }

      const resData = await response.json();
      sessionId.value = resData.sessionId;

    } catch (err: any) {"""
content = content.replace(old_import_fetch, new_import_fetch)

# Write to file
Path("electron/src/renderer/composables/useTranscriptionState.ts").write_text(content)
print("done")
