# Coding Conventions

**Analysis Date:** 2026-04-13

## Naming Patterns

**Files:**
- Python modules: `snake_case.py` (e.g., `audio_recorder.py`, `tab_manager.py`)
- UI modules mirror component name: `vu_meter.py`, `tab_transcription.py`
- Package init files: `__init__.py` present in `app/`, `app/ui/`, `app/ui_flet/`, `app/ui_flet/markdown/`

**Functions:**
- Public methods: `snake_case` (e.g., `transcribe()`, `is_online()`)
- Private/internal: prefix with single underscore `_snake_case` (e.g., `_require()`, `_optional()`, `_is_online_fn`, `_whisper_model`)

**Variables:**
- Local variables: `snake_case`
- Module-level constants: `UPPER_SNAKE_CASE` (e.g., `GOOGLE_API_KEY`, `GEMINI_MODEL`, `WHISPER_DEVICE`)
- Private module helpers: `_UPPER_SNAKE_CASE` prefix for internal constants (e.g., `_ROOT`)

**Types:**
- `TypeAlias` via `Literal`: `TranscriptionMode = Literal["auto", "gemini", "whisper"]`
- Class names: `PascalCase` (e.g., `Transcriber`, `TranscriptionError`)
- Custom exceptions: suffix with `Error` (e.g., `TranscriptionError`)

## Code Style

**Formatter:** `black`
- Config: `pyproject.toml` under `[tool.black]`
- Line length: 88 characters
- Target Python version: `py310`
- Excluded dirs: `.agent/`, `.venv/`, `docs/`

**Linting:**
- No linter (eslint, ruff, flake8) configured. Black is the only enforced tool.

**Run formatter:**
```bash
uv run black app/
```

## Import Organization

**Order (observed pattern):**
1. Standard library (`os`, `pathlib`, `typing`)
2. Third-party packages (`flet`, `google-genai`, `faster-whisper`)
3. Internal app imports (`from app.config import ...`)

**Path style:** Absolute package imports from project root (e.g., `from app.config import GEMINI_MODEL`), not relative imports.

## Module Docstrings

Every module begins with a docstring in the format:
```python
"""app.module_name — Short one-line description.

Extended description explaining routes, modes, and usage.

Usage:
    example_code_here
"""
```

Example: `app/transcriber.py`, `app/config.py`

## Error Handling

**Patterns:**
- Domain-specific exceptions extend `Exception` directly (e.g., `TranscriptionError`)
- Required config values use `RuntimeError` with a descriptive Portuguese message
- Helper `_require(key)` in `app/config.py` centralizes env var validation

## Logging

- No structured logging framework detected. Status and error information is surfaced via exceptions and UI state.

## Comments

**Section separators:** Dashes used to divide logical sections within modules:
```python
# ---------------------------------------------------------------------------
# Section Name
# ---------------------------------------------------------------------------
```

**Inline comments:** Used sparingly for non-obvious logic (e.g., `# Lazy-loaded on first use`)

**Dividers in classes:**
```python
# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------
```

## Function Design

**Parameters:** Type-annotated with `-> ReturnType` return hints where present
**Callables:** Typed as `callable` with `# type: ignore[valid-type]` when needed (Python 3.12 limitation workaround)
**Optional params:** Use `_optional(key, default)` pattern for env vars with defaults

## Commit Message Format

**Convention:** Conventional Commits style (`type: description`)

**Types observed:**
- `feat:` — New features
- `refactor:` — Code restructuring
- `chore:` — Tooling/config changes

**Format:**
```
type: Imperative sentence describing the change.
```

Body is optional; some commits include multi-line descriptions separated by commas.

**Language:** Mixed — recent commits (post-refactor) use English; older commits use Portuguese. New commits should use English.

## Branch Strategy

**Main branch:** `main`

**Feature branches:** `feat/<kebab-case-description>`
- Examples: `feat/electron-interface`, `feat/migrate-interface`, `feat/upload-files`, `feat/enhance-textfield`

**Merging:** Via pull requests (PR #1 observed in git log). No branch protection rules detected in local config.

## Review Requirements

- No CODEOWNERS file or GitHub branch protection config detected.
- PR workflow in use (GitHub), inferred from merge commit in history.

---

*Convention analysis: 2026-04-13*
