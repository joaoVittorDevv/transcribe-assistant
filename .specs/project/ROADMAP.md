# Roadmap

## Upcoming Milestones

### v0.2 — Enhanced Audio
- [ ] System audio capture improvements (PipeWire/PulseAudio loopback)
- [ ] Audio file format conversion / compression
- [ ] Configurable sample rate

### v0.3 — Session Management
- [ ] Session export (TXT, MD, PDF)
- [ ] Session search and filtering
- [ ] Prompt templates library
- [ ] Bulk session deletion

### v1.0 — Stable Release
- [ ] Comprehensive test coverage
- [ ] Installers for Linux (AppImage, .deb)
- [ ] Complete documentation

## Completed

### v0.1 — Core Transcription
- [x] CustomTkinter-based tab UI (dark theme)
- [x] Audio recording with RMS metering
- [x] Hybrid transcription routing (Gemini ↔ Groq)
- [x] TextReviewerAgent for Groq review
- [x] Audio file import with Silero VAD validation
- [x] SQLite persistence (sessions, prompts, keywords)
- [x] i18n support (pt/en)
- [x] Network connectivity monitoring
- [x] Native file dialogs (Zenity on Linux)
- [x] Settings modal for prompt/glossary

## Archived / Paused

### Electron UI (experimental — not active)
Branch: `feat/electron-interface` — Vue 3 + Tailwind + Vite scaffold exists in `electron/` but is not part of current build.
