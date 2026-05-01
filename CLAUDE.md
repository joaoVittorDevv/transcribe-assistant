# Transcribe Assistant

## Babysitter

This project uses babysitter for development workflow automation.

### Installed Processes
- `cradle/project-install` — Re-run project setup (updates profile, tools, CLAUDE.md)
- `cradle/bugfix` — Structured bug fixing workflow
- `cradle/feature-request` — Feature implementation workflow
- `gsd/plan-phase` — Plan implementation phases before coding
- `gsd/execute-plan` — Execute planned phases
- `gsd/code-review` — Automated code review

### Recommended Skills
- `/electron-development` — Electron main process, IPC, and window management
- `/python-pro` — Python backend (transcriber, server, audio engine)
- `/code-reviewer` — Automated code review (fills gap for solo dev)
- `/systematic-debugging` — Structured debugging for SSE/IPC issues
- `/tdd-workflow` — Test-driven development for building coverage

### Commands
- **Python:** `uv run python <script>`
- **Electron:** `cd electron && npm run start`
- **Tests:** `uv run pytest`
- **Lint:** `cd electron && npm run lint`

### Conventions
- **Python:** Black formatter (line-length 88), snake_case
- **TypeScript/Vue:** Strict mode, ES2022, camelCase/PascalCase
- **Commits:** Conventional commits (feat:, fix:, refactor:, docs:, chore:)
- **Branches:** `feat/<name>`, `fix/<name>`

### Methodology
Iterative convergence — plan phase, execute, verify, refine. Use `/gsd/plan-phase` before multi-file changes.
