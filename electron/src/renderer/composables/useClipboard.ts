import type { ElectronAPI } from '../types/global';

export function useClipboard() {
  const api = window.electronAPI as ElectronAPI;

  async function copyToClipboard(text: string): Promise<boolean> {
    return api.writeClipboard(text);
  }

  return { copyToClipboard };
}
