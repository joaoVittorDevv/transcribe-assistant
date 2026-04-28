# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup & Commands

```bash
# Install dependencies
uv sync

# Run the application
uv run main.py

# Format code
black .

# Development (watch mode)
uv run main.py
```

Environment variables are loaded from `.env` (copy from `.env.example`). Required keys: `GOOGLE_API_KEY`, `GROQ_API_KEY`.

## Architecture

```
main.py → app.config (validates .env) → MainWindow (CustomTkinter)
                                              │
                    ┌─────────────────────────┼─────────────────────────┐
                    ▼                         ▼                         ▼
           AudioRecorder              NetworkMonitor              Transcriber
        (sounddevice/parec)          (TCP ping 8.8.8.8)         (Gemini ↔ Groq)
                    │                         │                         │
                    └─────────────────────────┼─────────────────────────┘
                                              ▼
                                        database.py (SQLite)
```

### Audio capture
`AudioRecorder` streams audio via `sounddevice` at 16 kHz mono float32. For system audio it falls back to `parec` (PulseAudio) with resampling from 44.1 kHz → 16 kHz.

### Transcription routing
`Transcriber.transcribe()` has three modes:
- `"auto"`: tries Groq first → falls back to Gemini on failure
- `"gemini"`: forces Google Gemini Files API only
- `"groq"`: forces Groq Whisper + `TranscriptionReviewAgent` (grammar/punctuation correction via `llama-3.1-8b-instant`)

### Threading model
- Audio callback → `Queue` → `root.after()` polling → UI update (RMS VU meter)
- Transcription → `threading.Thread` → `Queue` → `root.after()` polling → UI update
- Network monitor → daemon `thread` → callback → `root.after()`

### Key files
| File | Role |
|------|------|
| `app/audio_recorder.py` | Audio capture from mic or system (parec) |
| `app/transcriber.py` | Routing Gemini ↔ Groq, title generation |
| `app/network_monitor.py` | TCP connectivity check (daemon thread) |
| `app/database.py` | SQLite: prompts, keywords, sessions tables |
| `app/ui/main_window.py` | CustomTkinter UI, tab management, event queues |
| `app/ui/vu_meter.py` | LED-style audio level meter |
| `app/ui/prompt_modal.py` | Prompt/glossary editor |
| `app/agents/transcription_review_agent.py` | Agno + Groq LLM for grammar correction |

### Knowledge Graph (graphify)

`graphify-out/GRAPH_REPORT.md` contains an extracted + inferred knowledge graph of the codebase:

- **393 nodes, 742 edges, 45 communities** — covers all modules and their relationships
- **God nodes** (most connected): `MainWindow` (54), `PromptModal` (46), `AudioRecorder` (39), `NetworkMonitor` (35), `Transcriber` (34)
- **Community hubs** — clusters like "Audio Recording Core", "Database Layer", "Transcription Agent API", "System Architecture", etc.
- **Hyperedges** — group relationships like "Audio Transcription Pipeline", "Cloud Transcription Stack", "UI Layer Components"

Use it for:
- Understanding how cross-module connections work (e.g., how `MainWindow` bridges audio, UI, and database layers)
- Finding the most important/abstraction-rich classes
- Discovering surprising inferred connections between modules
- Navigating via community structure instead of file-by-file grep

Files in `graphify-out/`:
| File | Purpose |
|------|---------|
| `GRAPH_REPORT.md` | Full graph report with communities, god nodes, hyperedges |
| `graph.json` | Raw graph data (nodes + edges) |
| `graph.html` | Interactive HTML visualization |
| `manifest.json` | Build metadata |
| `cost.json` | Token cost tracking |

After modifying code, run `graphify update .` to keep the graph current.

### Database schema
- `prompts`: id, nome, texto_prompt, is_default, criado_em
- `palavras_chave`: id, prompt_id (FK), palavra
- `sessions`: id, titulo, conteudo_texto, quantidade_interacoes, criado_em, atualizado_em
