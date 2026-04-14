export interface AudioStatus {
  recording: boolean;
  wav_path?: string;
}

export interface ElectronAPI {
  audioCommand(cmd: { action: string; mode?: string }): void;
  onRmsUpdate(callback: (value: number) => void): () => void;
  onAudioStatus(callback: (status: AudioStatus) => void): () => void;
  openFilePicker(accept: string[]): Promise<string | null>;
  readFile(path: string): Promise<ArrayBuffer | null>;
}

declare global {
  interface Window {
    electronAPI: ElectronAPI;
  }
}
