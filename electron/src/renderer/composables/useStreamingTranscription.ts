import { ref } from 'vue';
import { useDefaultPrompt } from './useDefaultPrompt';
import { useSocket } from './useSocket';

const isStreamingActive = ref(false); // Switch control (Batch vs Streaming)
const isRecordingStream = ref(false); // Active recording state for stream
const currentSessionId = ref<string | null>(null);

let socketListenersInitialized = false;

export function useStreamingTranscription() {
  const api = (window as any).electronAPI;
  const { promptData } = useDefaultPrompt();
  const { socket, connect: connectSocket } = useSocket();

  // Callbacks registered by components (e.g. TextEditor) to handle text updates
  const onInterimCallback = ref<((text: string) => void) | null>(null);
  const onFinalCallback = ref<((text: string) => void) | null>(null);

  function initSocketListeners() {
    if (socketListenersInitialized) return;
    if (!socket.value) return;

    socket.value.on('transcription:stream:interim' as any, (payload: any) => {
      if (payload.sessionId !== currentSessionId.value) return;
      if (onInterimCallback.value) {
        onInterimCallback.value(payload.text);
      }
    });

    socket.value.on('transcription:stream:final' as any, (payload: any) => {
      if (payload.sessionId !== currentSessionId.value) return;
      if (onFinalCallback.value) {
        onFinalCallback.value(payload.text);
      }
      cleanup();
    });

    socketListenersInitialized = true;
  }

  const startStreaming = (mode: 'mic' | 'system' | 'dual') => {
    if (isRecordingStream.value) return;

    console.log('[useStreamingTranscription] Starting Streaming ASR via Socket.IO...');
    
    // Ensure socket is connected
    connectSocket();
    if (!socket.value) {
      console.error('[useStreamingTranscription] Socket.IO instance not available');
      return;
    }

    initSocketListeners();

    // Generate local session ID
    const sessionId = 'stream_' + Math.random().toString(36).substring(2, 11) + '_' + Date.now();
    currentSessionId.value = sessionId;
    isRecordingStream.value = true;

    // Send record start to python engine via Electron Main IPC, including socket ID
    api.audioCommand({
      action: 'start',
      mode,
      isStreaming: true,
      sessionId: sessionId,
      socketId: socket.value.id || '',
      prompt: promptData.value.texto_prompt,
      keywords: promptData.value.keywords.join(', ')
    });
  };

  const stopStreaming = () => {
    if (!isRecordingStream.value) return;
    api.audioCommand({ action: 'stop' });
  };

  const cancelStreaming = () => {
    if (!isRecordingStream.value) return;
    api.audioCommand({ action: 'cancel' });
    if (socket.value && currentSessionId.value) {
      socket.value.emit('transcription:stream:cancel' as any, { sessionId: currentSessionId.value });
    }
    cleanup();
  };

  const cleanup = () => {
    isRecordingStream.value = false;
    currentSessionId.value = null;
    if (onInterimCallback.value) {
      onInterimCallback.value(''); // Clear interim text on cleanup
    }
  };

  return {
    isStreamingActive,
    isRecordingStream,
    currentSessionId,
    startStreaming,
    stopStreaming,
    cancelStreaming,
    onInterim: (cb: (text: string) => void) => {
      onInterimCallback.value = cb;
    },
    onFinal: (cb: (text: string) => void) => {
      onFinalCallback.value = cb;
    }
  };
}
