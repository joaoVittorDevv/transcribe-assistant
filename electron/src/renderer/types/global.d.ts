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

declare global {
  interface Window {
    electronAPI: ElectronAPI;
  }
}
