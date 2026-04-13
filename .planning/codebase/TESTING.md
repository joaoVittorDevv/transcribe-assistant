# Testing Patterns

**Analysis Date:** 2026-04-13

## Test Framework

**Runner:** Not configured.
- No `pytest.ini`, `conftest.py`, `jest.config.*`, or `vitest.config.*` detected in project root or `app/`.
- No test dependencies in `pyproject.toml` (`[dependency-groups]` contains only `black`).

**Assertion Library:** None configured.

**Run Commands:**
```bash
# No test runner configured — no test command available
```

## Test File Organization

**Location:** No test files exist in the project source tree (`app/` has no `test_*.py` or `*_test.py` files).

**Naming:** Not applicable — no tests present.

## Test Types

**Unit Tests:** Not present.

**Integration Tests:** Not present.

**E2E Tests:** Not present.

## CI/CD Pipeline

**GitHub Actions:** No `.github/workflows/` directory exists in the project root. No CI pipeline is configured.

**Deployment:** Not automated. No CD configuration detected.

## Coverage

**Requirements:** None enforced.

**Coverage tooling:** Not configured.

## What Exists Instead of Tests

Network connectivity validation is performed at runtime via `app/network_monitor.py`. Audio input validation is performed at runtime via `app/audio_validator.py`. These are runtime guards, not automated tests.

One historical commit (`bbed616`) mentions "network connectivity tests" — this refers to runtime checks, not an automated test suite.

## Recommendations for Adding Tests

When tests are added, follow this structure:

**Framework to add:** `pytest` (compatible with existing `uv` + Python 3.12 setup)

```bash
# Add to pyproject.toml dev dependencies:
uv add --dev pytest pytest-asyncio
```

**Suggested layout:**
```
tests/
├── conftest.py          # Shared fixtures
├── test_transcriber.py  # Unit tests for app/transcriber.py
├── test_config.py       # Unit tests for app/config.py
├── test_database.py     # Unit tests for app/database.py
└── test_audio_validator.py
```

**Mock targets when testing:**
- `app.transcriber.Transcriber` — mock `is_online_fn` callable
- `google.genai` client — mock for Gemini transcription tests
- `faster_whisper.WhisperModel` — mock for local transcription tests
- `sounddevice` — mock for audio recording tests

---

*Testing analysis: 2026-04-13*
