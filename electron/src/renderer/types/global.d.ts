export interface AudioStatus {
  recording: boolean;
  wav_path?: string;
  dual?: boolean;
  mic_wav_path?: string;
  sys_wav_path?: string;
  error?: string;
}

export interface AudioCommand {
  action: 'start' | 'stop' | 'cancel';
  mode?: 'mic' | 'system' | 'dual';
  isStreaming?: boolean;
  sessionId?: string;
  socketId?: string;
  prompt?: string;
  keywords?: string;
}

export interface ElectronAPI {
  audioCommand(cmd: AudioCommand): Promise<boolean>;
  onRmsUpdate(callback: (value: number) => void): () => void;
  onAudioStatus(callback: (status: AudioStatus) => void): () => void;
  openFilePicker(accept: string[]): Promise<string | null>;
  openDirectoryPicker(): Promise<string | null>;
  readFile(path: string): Promise<ArrayBuffer | null>;
  deleteFile(path: string): Promise<boolean>;
  writeClipboard(text: string): Promise<boolean>;
  insertTextAtCursor(text: string, tabId?: string): Promise<boolean>;
  onInsertText(callback: (payload: { text: string; tabId?: string }) => void): () => void;
  resetInsertionPoint(): void;
  onResetInsertionPoint(callback: () => void): () => void;
  updateSettingsTray(settings: { enabled: boolean; notificationsEnabled: boolean; interval: number; types: string }): void;
  updateAudioState(state: 'idle' | 'recording' | 'transcribing' | 'error'): void;
  onStopRecordingFromTray(callback: () => void): () => void;
}

declare global {
  interface Window {
    electronAPI: ElectronAPI;
  }
}
