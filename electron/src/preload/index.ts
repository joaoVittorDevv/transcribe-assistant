import { contextBridge, ipcRenderer } from 'electron';

contextBridge.exposeInMainWorld('electronAPI', {
  platform: process.platform,
  writeClipboard: (text: string) => ipcRenderer.invoke('write-clipboard', text),
});
