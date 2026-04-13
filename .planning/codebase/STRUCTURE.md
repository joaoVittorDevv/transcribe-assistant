# Codebase Structure

**Analysis Date:** 2026-04-13

## Directory Layout

```
transcribe-assistant/
├── app/                    # All application source code
│   ├── ui_flet/            # Primary Flet UI (active)
│   │   ├── markdown/       # Markdown editor sub-components
│   │   ├── main_app.py     # Root Flet component + FletApp class
│   │   ├── tab_manager.py  # Multi-tab editor container
│   │   ├── tab_transcription.py  # Individual tab widget
│   │   ├── sidebar.py      # Prompt selector panel
│   │   ├── vu_meter.py     # Animated LED audio level meter
│   │   ├── markdown_editor.py    # Markdown edit/preview toggle
│   │   ├── history_window.py     # Session history modal
│   │   └── prompt_modal.py       # Prompt create/edit modal
│   ├── ui/                 # Legacy CustomTkinter UI (kept for reference)
│   │   ├── main_window.py
│   │   ├── sidebar.py
│   │   ├── vu_meter.py
│   │   ├── markdown_editor.py
│   │   ├── history_window.py
│   │   ├── prompt_modal.py
│   │   └── native_dialog.py      # Cross-platform file open dialog
│   ├── utils/              # Shared helpers
│   │   ├── i18n_manager.py       # Runtime locale switching wrapper
│   │   └── clipboard_manager.py  # Clipboard write helper
│   ├── audio_recorder.py   # sounddevice/parec capture + RMS metering
│   ├── audio_validator.py  # File extension allow-list
│   ├── transcriber.py      # Gemini/Whisper routing + title generation
│   ├── network_monitor.py  # Background TCP connectivity checker
│   ├── database.py         # SQLite schema + CRUD
│   ├── config.py           # .env loader, typed constants, i18n init
│   └── __init__.py
├── assets/                 # Static assets served by Flet
│   └── logo.png            # Application logo
├── locales/                # i18n JSON files
│   ├── pt.json             # Portuguese (default)
│   └── en.json             # English
├── scripts/
│   └── connectivity_tests/ # Ad-hoc scripts for testing API connectivity
├── .planning/              # GSD planning documents
│   └── codebase/           # Auto-generated codebase analysis
├── main_flet.py            # Flet entry point (primary)
├── main.py                 # CustomTkinter entry point (legacy)
├── pyproject.toml          # Project metadata + dependencies (uv)
├── uv.lock                 # Lockfile
└── transcriber_data.db     # SQLite database (runtime, not committed)
```

## Directory Purposes

**`app/`:**
- Purpose: All application Python code.
- Contains: Core services (backend), two UI implementations, utilities.
- Key files: `config.py` (must be imported first), `database.py`, `transcriber.py`

**`app/ui_flet/`:**
- Purpose: Active primary UI built with Flet.
- Contains: One class per widget/view; sub-package `markdown/` for editor components.
- Key files: `main_app.py` (root container), `tab_manager.py`, `sidebar.py`

**`app/ui_flet/markdown/`:**
- Purpose: Markdown editing components split by concern.
- Contains: `toolbar.py` (formatting buttons), `preview.py` (rendered view), `text_utils.py` (formatting helpers)

**`app/ui/`:**
- Purpose: Legacy CustomTkinter UI; preserved during migration to Flet.
- Contains: Parallel widget set to `ui_flet/`.
- Key file: `native_dialog.py` — still imported by `ui_flet/main_app.py` for the cross-platform file open dialog.

**`app/utils/`:**
- Purpose: Stateless helpers shared between UI implementations.
- Key file: `i18n_manager.py` — wraps `python-i18n` to expose `i18n.get(key)` and `i18n.set_language(lang)` without importing the raw library everywhere.

**`assets/`:**
- Purpose: Static files referenced by `ft.run(assets_dir="assets")`.
- Generated: No. Committed: Yes.

**`locales/`:**
- Purpose: Internationalization string files consumed by `python-i18n`.
- Naming: `{locale}.json` — currently `pt.json` and `en.json`.

**`scripts/connectivity_tests/`:**
- Purpose: Developer scripts for manually verifying Gemini API and network connectivity.
- Not part of the application runtime.

## Key File Locations

**Entry Points:**
- `main_flet.py`: Flet UI startup (primary)
- `main.py`: CustomTkinter startup (legacy)

**Configuration:**
- `app/config.py`: Single source of truth for all runtime settings; validates required env vars at import time.

**Core Services:**
- `app/transcriber.py`: Transcription backend router
- `app/audio_recorder.py`: Audio capture
- `app/network_monitor.py`: Connectivity state
- `app/audio_validator.py`: Allowed audio file extensions

**Persistence:**
- `app/database.py`: All SQLite operations; `initialize_db()` called at startup

**Primary UI Root:**
- `app/ui_flet/main_app.py`: `FletApp` class + `init_app(page)` function

**Testing:**
- `scripts/connectivity_tests/`: Manual integration tests only; no automated test suite detected.

## Naming Conventions

**Files:**
- `snake_case.py` for all Python modules.
- Widget/view files named after their UI role: `tab_manager.py`, `vu_meter.py`, `sidebar.py`.

**Directories:**
- `snake_case` for all directories.
- `ui_flet/` vs `ui/` distinguishes the two UI implementations.

**Classes:**
- `PascalCase`: `AudioRecorder`, `Transcriber`, `FletApp`, `TabManager`
- Exception classes suffixed with `Error`: `TranscriptionError`

## Where to Add New Code

**New backend service (no UI):**
- Implementation: `app/{service_name}.py`
- Instantiate in `app/ui_flet/main_app.py::FletApp.__init__` alongside existing services.

**New Flet UI component/widget:**
- Implementation: `app/ui_flet/{component_name}.py`
- Import and instantiate in `main_app.py::_build_ui()` or the relevant parent component.

**New Flet sub-component for an existing widget:**
- If it grows complex, create a sub-package (e.g. `app/ui_flet/markdown/`) with an `__init__.py`.

**New database table or query:**
- Add schema to `initialize_db()` in `app/database.py` using `CREATE TABLE IF NOT EXISTS`.
- Add CRUD functions in the same file, grouped by table.
- Add migration `ALTER TABLE` block (guarded by `except sqlite3.OperationalError: pass`) if adding a column to an existing table.

**New i18n string:**
- Add key-value to both `locales/pt.json` and `locales/en.json`.
- Reference via `i18n.get("key")` using the `i18n_manager` import.

**New configuration value:**
- Add to `app/config.py` using `_require(key)` (mandatory) or `_optional(key, default)` (optional).

**New static asset:**
- Place in `assets/` — Flet serves this directory automatically when launched via `ft.run(..., assets_dir="assets")`.

## Special Directories

**`.planning/`:**
- Purpose: GSD planning and codebase analysis documents.
- Generated: Partially (codebase docs auto-generated by GSD mapper).
- Committed: Yes.

**`transcriber_data.db`:**
- Purpose: Runtime SQLite database file.
- Generated: Yes (created by `initialize_db()` on first run).
- Committed: No (should be in `.gitignore`).

---

*Structure analysis: 2026-04-13*
