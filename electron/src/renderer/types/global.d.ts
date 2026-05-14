export interface AudioStatus {
  recording: boolean;
  wav_path?: string;
  dual?: boolean;
  mic_wav_path?: string;
  sys_wav_path?: string;
  error?: string;
}

export interface ElectronAPI {
  audioCommand(cmd: { action: string; mode?: string }): Promise<boolean>;
  onRmsUpdate(callback: (value: number) => void): () => void;
  onAudioStatus(callback: (status: AudioStatus) => void): () => void;
  openFilePicker(accept: string[]): Promise<string | null>;
  readFile(path: string): Promise<ArrayBuffer | null>;
  deleteFile(path: string): Promise<boolean>;
  insertTextAtCursor(text: string): Promise<boolean>;
  onInsertText(callback: (text: string) => void): () => void;
  resetInsertionPoint(): void;
  onResetInsertionPoint(callback: () => void): () => void;
}

declare global {
  interface Window {
    electronAPI: ElectronAPI;
  }
}
