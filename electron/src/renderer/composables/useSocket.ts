import { ref } from 'vue';
import { io, Socket } from 'socket.io-client';
import { ServerToClientEvents, ClientToServerEvents } from '../types/socket';

type AppSocket = Socket<ServerToClientEvents, ClientToServerEvents>;

const socket = ref<AppSocket | null>(null);
const isConnected = ref(false);

export function useSocket() {
  const connect = () => {
    if (socket.value) return;

    socket.value = io('http://localhost:18763', {
      reconnectionDelayMax: 10000,
    });

    socket.value.on('connect', () => {
      isConnected.value = true;
      console.log('[Socket.IO] Connected with ID:', socket.value?.id);
    });

    socket.value.on('disconnect', () => {
      isConnected.value = false;
      console.log('[Socket.IO] Disconnected');
    });
  };

  const disconnect = () => {
    if (socket.value) {
      socket.value.disconnect();
      socket.value = null;
      isConnected.value = false;
    }
  };

  return {
    socket,
    isConnected,
    connect,
    disconnect,
  };
}
