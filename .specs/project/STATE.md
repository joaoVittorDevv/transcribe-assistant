# State

**Last updated:** 2026-04-21

## Decisions

| ID | Decision | Reason | Date |
|----|----------|--------|------|
| D001 | Use CustomTkinter as primary UI | Mature, Python-native, works well with `uv` | 2026-02 |
| D002 | Groq first → Gemini fallback in auto mode | Groq is faster and cheaper; fallback ensures reliability | 2026-03 |
| D003 | SQLite for local persistence | Simple, zero-config, sufficient for single-user desktop app | 2026-02 |
| D004 | Silero VAD for audio validation | FFmpeg/PyAV handles all formats robustly | 2026-04 |
| D005 | Audio import validation before transcription | Prevents wasting API quota on non-speech audio | 2026-04 |

## Blockers

| Blocker | Impact | Notes |
|---------|--------|-------|
| None | — | — |

## Lessons

| Lesson | Evidence |
|--------|----------|
| Network monitoring must be non-blocking | Initial blocking ping caused UI freezes; fixed with daemon Thread |
| Groq 25MB limit requires file size checks | Caught via `audio_path.stat().st_size > 25 * 1024 * 1024` in `transcriber.py` |
| Audio format must match Whisper expectations | 16kHz mono float32 is optimal for Whisper |
| CTkToplevel needs `after()` defer on Linux | `_delayed_init()` pattern in `prompt_modal.py` and `history_window.py` |
| `grab_set()` can fail on Linux | Wrapped in try/except with `_safe_grab()` pattern |
| `faster-whisper` VAD needs FFmpeg/PyAV | `decode_audio()` handles format conversion automatically |

## Deferred Ideas

- Local faster-whisper transcription (GPU required = too slow in practice)
- Session collaboration / cloud sync
- Custom Whisper model fine-tuning
- Flet UI (experimental `app/ui_flet/` exists but not active)

## Current Work

**Active branch:** `main`

Active development on CustomTkinter UI with audio recording and hybrid transcription.
