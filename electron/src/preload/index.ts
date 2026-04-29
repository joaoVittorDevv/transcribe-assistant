import { contextBridge, ipcRenderer } from 'electron';

export interface AudioStatus {
  recording: boolean;
  wav_path?: string;
}

export interface ElectronAPI {
  audioCommand(cmd: { action: string; mode?: string }): Promise<boolean>;
  onRmsUpdate(callback: (value: number) => void): () => void;
  onAudioStatus(callback: (status: AudioStatus) => void): () => void;
  openFilePicker(accept: string[]): Promise<string | null>;
  readFile(path: string): Promise<ArrayBuffer | null>;
  deleteFile(path: string): Promise<boolean>;
  insertTextAtCursor(text: string): void;
  onInsertText(callback: (text: string) => void): () => void;
}

const electronAPI: ElectronAPI = {
  audioCommand(cmd) {
    // Bug 1a fix: return Promise so caller can await the result
    return ipcRenderer.invoke('audio-command', cmd);
  },

  onRmsUpdate(callback) {
    const handler = (_event: Electron.IpcRendererEvent, value: number) => callback(value);
    ipcRenderer.on('rms-update', handler);
    return () => ipcRenderer.removeListener('rms-update', handler);
  },

  onAudioStatus(callback) {
    const handler = (_event: Electron.IpcRendererEvent, status: AudioStatus) => callback(status);
    ipcRenderer.on('audio-status', handler);
    return () => ipcRenderer.removeListener('audio-status', handler);
  },

  async openFilePicker(accept: string[]) {
    return ipcRenderer.invoke('open-file-dialog', accept);
  },

  async readFile(filePath: string): Promise<ArrayBuffer | null> {
    const result = await ipcRenderer.invoke('read-file', filePath);
    if (result === null) return null;
    // result is a Buffer from Node — convert to ArrayBuffer
    return result.buffer.slice(result.byteOffset, result.byteOffset + result.byteLength);
  },

  async deleteFile(filePath: string) {
    return ipcRenderer.invoke('delete-file', filePath);
  },

  insertTextAtCursor(text: string) {
    ipcRenderer.invoke('insert-text-at-cursor', text);
  },

  onInsertText(callback) {
    const handler = (_event: Electron.IpcRendererEvent, text: string) => callback(text);
    ipcRenderer.on('insert-text', handler);
    return () => ipcRenderer.removeListener('insert-text', handler);
  },
};

contextBridge.exposeInMainWorld('electronAPI', electronAPI);
