# Phase 2: FastAPI Backend Wrapper - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-13
**Phase:** 2-fastapi-wrapper
**Areas discussed:** Streaming strategy, Backend integration, Connection resilience

---

## Streaming Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Server-Sent Events (SSE) | Unidirectional server→client streaming | ✓ |
| WebSocket | Bidirectional, more complex | |
| Polling | Inefficient, not real-time | |

**User's choice:** SSE — unidirecional, apenas servidor envia para front-end
**Notes:** Connection must be resilient with auto-reconnect

---

## Text Format

| Option | Description | Selected |
|--------|-------------|----------|
| Plain text string | Each SSE data: line is a plain UTF-8 string chunk | ✓ |
| JSON with metadata | Wrapped chunks with request_id, timestamp, etc. | |

**User's choice:** Plain text string
**Notes:** Simple is better for this use case

---

## Backend Integration

| Option | Description | Selected |
|--------|-------------|----------|
| FastAPI wrapping Transcriber directly | Integrated into existing app process, not separate service | ✓ |
| Separate microservice | Would require more infrastructure | |

**User's choice:** Wrapped directly in the TranscriberAgent
**Notes:** Integration should be direct, not as a separate service

---

## Connection Handling

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-reconnect with exponential backoff | Client reconnects automatically, delay increases on each failure | ✓ |
| Fixed delay reconnect | Simpler but less resilient | |
| No reconnection | Connection must be re-established manually | |

**User's choice:** Auto-reconnect, exponential backoff, state persistence
**Notes:** Server must maintain transcription state to support reconnection resume

---

## Deferred Ideas

- Whisper chunked streaming (returns all at once today) — noted for future enhancement
