# Coding Conventions

**Analysis Date:** 2026-04-14

## Python

**Version:** Python 3.12+ (requires `>=3.12`)

**Formatter:** Black
- Line length: 88 characters
- Target version: py310
- Excluded paths: `.agent`, `.venv`, `docs`

**Package Manager:** `uv`
- Dependencies managed via `pyproject.toml`
- Dev dependencies in `[dependency-groups]` section

**Import Organization:**
1. Standard library (`os`, `pathlib`, `typing`)
2. Third-party packages (`fastapi`, `sounddevice`, `google-genai`)
3. Internal app imports (`from app.config import ...`)

**Module Docstrings:**
```python
"""app.module_name — Short one-line description.

Extended description explaining purpose and usage.
"""
```

## Vue / TypeScript (Electron)

**Version:** TypeScript with strict mode enabled

**tsconfig (`electron/tsconfig.json`):**
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "jsx": "preserve"
  }
}
```

**Path Alias:** `@/*` maps to `src/renderer/*`

**Naming Conventions:**
- Vue components: PascalCase (e.g., `AudioVisualizer.vue`, `RecordButton.vue`)
- TypeScript files: camelCase (e.g., `useTranscriptionState.ts`)
- Composables: `use*` prefix

**Style Settings:**
- `esModuleInterop: true`
- `allowSyntheticDefaultImports: true`
- `isolatedModules: true`

## Git Commit Style

**Convention:** Conventional Commits

**Format:**
```
type(scope): description
```

**Types:**
- `feat:` — New feature
- `fix:` — Bug fix
- `docs:` — Documentation
- `chore:` — Maintenance
- `refactor:` — Code restructure

**Examples:**
- `feat(electron): Phase 1 Electron UI + Phase 2 FastAPI SSE wrapper`
- `docs(phase3): create 03-01-PLAN.md audio integration plan`
- `fix: Corrige a inicialização de janelas modais no Linux`

**Language:** Recent commits use English; older commits used Portuguese

---

*Convention analysis: 2026-04-14*