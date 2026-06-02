export interface TranscriptionChunkPayload {
  seq: number;
  text: string;
  sessionId: string;
}

export interface TranscriptionStatusPayload {
  phase: string;
  message: string;
  sessionId: string;
}

export interface TranscriptionErrorPayload {
  message: string;
  sessionId: string;
}

export interface TranscriptionDonePayload {
  sessionId: string;
  totalChunks: number;
}

export interface ServerToClientEvents {
  "transcription:chunk": (payload: TranscriptionChunkPayload, callback: (ack: { status: string }) => void) => void;
  "transcription:status": (payload: TranscriptionStatusPayload) => void;
  "transcription:error": (payload: TranscriptionErrorPayload) => void;
  "transcription:done": (payload: TranscriptionDonePayload) => void;
}

export interface ClientToServerEvents {
  "transcription:cancel": (payload: { sessionId: string }) => void;
}
