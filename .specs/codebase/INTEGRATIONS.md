# External Integrations

## Cloud Transcription

### Google Gemini API

**Service:** Google AI Gemini (cloud transcription)
**Purpose:** Primary cloud transcription engine via Files API; also used for audio classification in validator
**Location:** `app/transcriber.py` → `_transcribe_gemini()`, `app/audio_validator.py` → `_classify_with_gemini()`
**Configuration:** `GOOGLE_API_KEY`, `GEMINI_MODEL` (default: `gemini-2.0-flash`)
**Authentication:** API key via `google-genai` client
**Key endpoints:**
- `client.files.upload()` — Upload audio to Gemini Files API
- `client.models.generate_content()` — Request transcription / classification

### Groq Whisper API

**Service:** Groq Cloud (Whisper transcription)
**Purpose:** Fast cloud transcription with automatic review
**Location:** `app/transcriber.py` → `_transcribe_groq()`
**Configuration:** `GROQ_API_KEY`, `GROQ_REVIEW_MODEL` (default: `llama-3.1-8b-instant`)
**Authentication:** API key via `groq` client
**Key endpoints:**
- `client.audio.transcriptions.create()` — Transcribe audio (Whisper-large-v3-turbo)
- `client.chat.completions.create()` — Text review via TextReviewerAgent

## AI Agents

### TextReviewerAgent

**Purpose:** Grammar and punctuation correction on Groq transcriptions; keyword near-match flagging
**Location:** `app/agents/text_reviewer_agent.py`
**Model:** `GROQ_REVIEW_MODEL` (default: `llama-3.1-8b-instant`)
**System Prompt:** Portuguese BR grammar correction with glossary near-match detection using `difflib.SequenceMatcher`

## Network Monitoring

**Service:** TCP connectivity check
**Purpose:** Determine online/offline status for routing decisions
**Location:** `app/network_monitor.py` → `NetworkMonitor`
**Configuration:** `NETWORK_PING_HOST` (default: `8.8.8.8`), `NETWORK_PING_PORT` (default: `53`)
**Implementation:** `socket.create_connection()` with 3-second timeout in daemon thread
**Communication:** `on_status_change` callback → posts to `_ui_queue`

## Audio Validation

### Silero VAD

**Service:** Voice Activity Detection via `faster-whisper`
**Purpose:** Determine speech ratio in imported audio files
**Location:** `app/audio_validator.py` → `_compute_speech_ratio()`
**Implementation:** `faster_whisper.vad.get_speech_timestamps()` + `decode_audio()` (PyAV/FFmpeg)
**Thresholds:**
- >40% speech → accept (clearly speech)
- <15% speech → reject (not speech)
- 15-40% → Gemini classifies if online, else accept with warning

## Database

**System:** SQLite (built-in Python)
**Purpose:** Local persistence for sessions, prompts, keyword glossaries
**Location:** `app/database.py`
**Schema:**
- `prompts` — User-defined transcription instructions with `is_default` flag
- `palavras_chave` — Glossary keywords linked to prompts (CASCADE delete)
- `sessions` — Transcription history with incremental updates and interaction count
**Migration:** `ALTER TABLE` wrapped in try/except for forward-compatibility

## i18n

**Service:** `python-i18n`
**Purpose:** Multi-language UI support
**Location:** `locales/` directory with JSON files (`pt.json`, `en.json`)
**Configuration:** `APP_LANGUAGE` env var (default: `pt`); `i18n.set("locale", ...)` at runtime

## Audio Hardware

**Devices:** System microphones and system audio via `sounddevice`
**Detection:** `sd.query_devices()` for device enumeration
**PipeWire/PulseAudio:** Virtual sources detected by name pattern matching (`"pipewire"`, `"pulse"`, `"default"`)
**Monitor devices:** Detected via `"Monitor of"` pattern in device name on Linux

## Native Dialogs

**Service:** Zenity (Linux) / tkinter (other OS)
**Purpose:** Native file picker for audio import
**Location:** `app/ui/native_dialog.py`
**Implementation:** `subprocess.run(["zenity", "--file-selection", ...])` with 5-minute timeout
**Fallback:** `tkinter.filedialog.askopenfilename()` if Zenity unavailable
