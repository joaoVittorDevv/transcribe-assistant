# Code Conventions

## Naming Conventions

### Files

- **Modules:** `snake_case.py` (e.g., `audio_recorder.py`, `transcriber.py`)
- **Packages:** `snake_case/` (e.g., `app/ui/`)
- **Tests:** `test_*.py` in `tests/` directory
- **Entry point:** `main.py` at project root

### Functions/Methods

- **Methods:** `snake_case` (e.g., `start_recording`, `transcribe`)
- **Private methods:** `_leading_underscore` (e.g., `_audio_callback`, `_transcribe_groq`)
- **Callbacks:** `on_*` pattern (e.g., `on_rms`, `on_network_change`)
- **Internal helpers:** `_leading_underscore` (e.g., `_resolve_device`, `_build_system_instruction`)
- **Properties:** `snake_case` with `@property` decorator (e.g., `is_online`)

### Variables

- **Instance variables:** `_leading_underscore` for mutable state (e.g., `_frames`, `_stream`, `_is_recording`)
- **Module-level constants:** `UPPER_SNAKE_CASE` at module level (e.g., `_SAMPLE_RATE`, `_CHANNELS`)
- **Function args:** `snake_case` (e.g., `audio_path`, `prompt_text`)
- **Private module-level queues:** `_leading_underscore` (e.g., `_ui_queue`)

### Types

- **Type aliases:** `PascalCase` ending in `Mode` or `Type` (e.g., `TranscriptionMode = Literal["auto", "gemini", "groq"]`)
- **Named tuples:** `PascalCase` (e.g., `ValidationResult(NamedTuple)`)
- **Custom exceptions:** `PascalCase` ending in `Error` (e.g., `TranscriptionError`)
- **Dataclasses:** `PascalCase` (e.g., `ReviewResult`)

## Code Organization

### Import Order

1. Standard library
2. Third-party packages
3. Local/relative imports (`from app.config import ...`)

### File Structure (per module)

```
"""Module docstring."""

import standard_lib
import third_party
from app.local import something

# Module-level constants (UPPER_SNAKE_CASE)

class MyClass:
    """Class docstring with Args, Returns, Raises sections."""

    def __init__(self) -> None:
        self._private_state: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def public_method(self) -> None:
        ...

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _private_method(self) -> None:
        ...
```

### Docstring Style

Google-style docstrings for public APIs:

```python
def transcribe(
    self,
    audio_path: Path,
    prompt_text: str,
    keywords: list[str],
    mode: TranscriptionMode = "auto",
) -> str:
    """Transcribe an audio file and return the resulting text.

    Args:
        audio_path: Path to the WAV file to transcribe.
        prompt_text: The active prompt's instruction text (used by Gemini).
        keywords: Glossary words (used by both backends differently).
        mode: Transcription mode — "auto" | "gemini" | "groq".

    Returns:
        Transcribed text string.

    Raises:
        TranscriptionError: If the selected backend fails and no fallback exists.
    """
```

## Type Safety

- Type annotations present throughout (`def foo() -> str:`)
- No enforced type checker (mypy unchecked)
- `type: ignore[return-value]` used where mypy would complain about `None`

## Error Handling

- Custom exceptions for domain errors (`TranscriptionError`)
- Context managers for resource cleanup (`_connect()`)
- Graceful degradation where possible (e.g., Groq review failure returns raw text, Gemini unavailable falls back to Groq)
- Debug prints via `print(f"[DEBUG] ...")` for development tracing
- `except Exception as exc: # noqa: BLE001` used for broad exception catches in callbacks

## Comments

- Module docstrings at file top
- Class docstrings with Args/Returns/Raises
- Section dividers for large classes (`# ==================================================================`)
- `# noqa: ANN001` for unused sounddevice callback `status` param
- `# noqa: BLE001` for broad exception catches

## UI-Specific Conventions (CustomTkinter)

- Window class inherits from `ctk.CTk`
- Sub-windows inherit from `ctk.CTkToplevel`
- Use `self.after()` for deferred operations on Linux (CTkToplevel race condition fix)
- `grab_set()` wrapped in try/except for Linux compatibility
- Dark theme set via `ctk.set_appearance_mode("dark")`
