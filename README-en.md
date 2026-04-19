<p align="center">
  <img src="assets/assist_transcribe_1x1.png" alt="Transcribe Assistant Logo" width="120" />
</p>

<h1 align="center">Transcribe Assistant</h1>

The **Transcribe Assistant** is a cross-platform desktop application built with Python (Flet) engineered to optimize audio annotation pipelines. It relies on a hybrid routing engine that combines Google Gemini cloud capabilities with the fast Groq API (Whisper-large-v3-turbo) as fallback — eliminating the need for local GPU to achieve offline-quality transcription.

The primary design principle is robust resilience to connectivity drops, serving seamless transcription online.

## ✨ Key Features

- **Hybrid Routing Network:** Smart fallback between Google Gemini and Groq (Whisper cloud), with graceful transitions and intelligent error recovery.
- **Multi-Tab Workspace:** Manage and isolate multiple audio transcription sessions simultaneously through an intuitive tab-based interface.
- **Internationalization (i18n):** Built-in and extensive multilingual support for the user interface out of the box.
- **Ongoing Recording Controls:** Active capabilities to immediately abort and discard any ongoing audio recording flow.

## 🚀 Architecture & Hybrid Routing

The core engine supports 3 execution modes:
1. **Auto Mode ("auto"):** Pings the tracked host (`NETWORK_PING_HOST`) via `network_monitor.py`. Upon successful internet detection, it routes audio via `Files API` to Google Gemini. If the connection fails, it falls back to the Groq API (`whisper-large-v3-turbo`).
2. **Force Cloud ("gemini"):** Bypasses all fallback checks, targeting your `.env` configured model (e.g., `gemini-2.0-flash`) via Agno Agent for maximum accuracy.
3. **Force Groq ("groq"):** Uses exclusively the Groq API with `whisper-large-v3-turbo`. Fast, no local GPU required, requires internet.

### Technology Stack
- **Language & Standards:** Python 3.12+ wrapped by `uv`. Codebase follows `black` formatting.
- **UI (Primary):** `Flet` (async framework based on Flutter).
- **Cloud Transcription:** `google-genai` (Gemini) + `groq` (Whisper cloud).
- **Agent Orchestration:** `agno` (agent framework with streaming support).
- **Audio Capture:** `sounddevice` paired with `soundfile`.
- **Database:** Built-in SQLite via `app/database.py`.

---

## 🛠️ Setup & Installation Guide

This is an open-source, highly adaptable personal baseline. Clone, hack, and adjust it for your own workflow requirements.

### 1. Cloning the Repository & Building the Environment
It is highly recommended to bootstrap using `uv` over standard pip tooling for instant sync speeds.

```bash
git clone <your-repo-link-here> transcribe-assistant
cd transcribe-assistant

# Bootstrap dependencies resolved over pyproject.toml
uv sync
```

### 2. Configure Environment Secrets (`.env`)
The environment manifest explicitly binds underlying backend behaviors, local hardware topologies, and remote keys.
Duplicate and rename the blueprint:
```bash
cp .env.example .env
```

**Crucial Variables to Define:**
- `GOOGLE_API_KEY`: Required for Google Gemini transcription. Generate at aistudio.google.com.
- `GROQ_API_KEY`: Required for Groq Whisper cloud fallback. Generate at console.groq.com.
- `GEMINI_MODEL`: Standard target is `gemini-2.0-flash` or `gemini-1.5-pro`.

### 3. Application Execution
Execute the Python entry module once your `.env` is loaded with API specifications:

```bash
uv run main.py
```

This commands standardizes configurations across `app.config`, mounts the initial schemas in your `transcriber_data.db` via SQLite execution handlers, and finally injects the CustomTkinter root window layout.

---

## 🗃️ Deep Dives Into Code Layers
If modifying or maintaining the app, understand its segmented nodes:
- **`app/ui/`**: Houses all view controllers, modals, component binding events, and CustomTkinter layouts.  
- **`app/audio_recorder.py`**: Intercepts buffered data streams securely inside the OS to output safe WAV temporary files locally.  
- **`app/database.py`**: A schema utility mapping execution footprints out to logs or recorded sessions (`initialize_db()`).
- **`app/network_monitor.py`**: Implements silent threaded background check-ins without disrupting the Tkinter mainloop rendering pipeline.

## Contributing
You are encouraged to tweak and submit edits to the local fallback execution handlers within `transcriber.py` or scale the current internal SQLite databases as needed!
