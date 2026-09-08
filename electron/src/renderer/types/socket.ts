export interface TranscriptionChunkPayload {
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
  text: string;
}

/** Authoritative job state from GET /jobs/{id} — used to reconcile after reconnect. */
export interface TranscriptionJobState {
  id: string;
  status: string;
  provider: string | null;
  text: string;
  lastError: string | null;
  nextRetryAt: string | null;
  audioPaths: string[];
  updatedAt: string;
}

export interface ServerToClientEvents {
  "transcription:chunk": (payload: TranscriptionChunkPayload) => void;
  "transcription:status": (payload: TranscriptionStatusPayload) => void;
  "transcription:error": (payload: TranscriptionErrorPayload) => void;
  "transcription:done": (payload: TranscriptionDonePayload) => void;
}

export interface ClientToServerEvents {
  "transcription:cancel": (payload: { sessionId: string }) => void;
}
