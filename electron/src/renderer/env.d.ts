export {};

declare global {
  interface Window {
    electronAPI: {
      audioCommand(cmd: { action: string; mode?: string }): Promise<boolean>;
      onRmsUpdate(callback: (value: number) => void): () => void;
      openFilePicker(accept: string[]): Promise<string | null>;
    };
  }
}
