export {};

declare global {
  interface Window {
    electronAPI: {
      audioCommand(cmd: { action: string; mode?: string }): void;
      onRmsUpdate(callback: (value: number) => void): () => void;
      openFilePicker(accept: string[]): Promise<string | null>;
    };
  }
}
