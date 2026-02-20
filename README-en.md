# Transcribe Assistant

The **Transcribe Assistant** is a cross-platform desktop application built with Python (CustomTkinter) engineered to optimize audio annotation pipelines. It relies on a distinct hybrid routing engine that falls back gracefully between local, privacy-centric AI models utilizing GPU/CPU (`faster-whisper`), and robust cloud endpoints via Google Gemini.

The primary design principle is robust resilience to connectivity drops, serving seamless transcription offline or online.

## 🚀 Architecture & Hybrid Routing

The core engine (`app/transcriber.py`) supports 3 execution modes:
1. **Auto Mode ("auto"):** Pings the tracked host (`NETWORK_PING_HOST`) via `network_monitor.py`. Upon successful internet detection, it routes audio metadata via `Files API` to Google Gemini. If the connection fails or drops, it transparently rolls over to the local parameter-frozen Whisper model.
2. **Force Cloud ("gemini"):** Bypasses all local execution checks to favor pinpoint accuracy by targeting your `.env` configured model (e.g., `gemini-2.0-flash`).
3. **Force Offline ("whisper"):** Bypasses tracking completely, triggering exclusively the `faster-whisper` ecosystem. The engine lazy-loads the transformer checkpoint, avoiding heavy VRAM allocation until inferencing is mandated. It defaults to CPU (int8) quantization if the host's CUDA toolkit misbehaves.

### Technology Stack
- **Language & Engine:** Python 3.12+ wrapped by `uv` packaging.
- **UI:** `customtkinter` (Native Performant GUIs over Tk).
- **Offline Transcriptions:** `faster-whisper`.
- **Cloud Transcriptions:** `google-genai`.
- **Audio Capture Node:** `sounddevice` paired with `soundfile`.
- **Database Architecture:** Built-in SQLite via `app/database.py`.

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
- `GOOGLE_API_KEY`: Strictly required for Cloud/Auto execution. Generate at aistudio.google.com.
- `GEMINI_MODEL`: Standard target is `gemini-2.0-flash` or `gemini-1.5-pro`.
- `WHISPER_MODEL`: Controls base quantization capacity (`base`, `small`, `medium`). The `base` and `small` profiles hover safely on 4GB VRAM GPU machines.
- `WHISPER_DEVICE`: Declare either `cuda` or manually shift to `cpu`.
- `WHISPER_COMPUTE_TYPE`: Use `float16` for Nvidia clusters natively, `int8` for limited setups, or `float32` alongside CPU mode.

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
