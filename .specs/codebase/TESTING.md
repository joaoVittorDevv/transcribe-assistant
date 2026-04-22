# Testing Infrastructure

## Test Frameworks

- **Unit/Integration:** `pytest` (in `tests/` — directory exists but is empty)
- **Coverage:** None currently
- **E2E:** None

## Test Organization

**Location:** `tests/` directory exists but is empty
**Naming:** Not established (no test files found)
**Structure:** Not established

## Testing Patterns

No test files currently exist in the project. The `tests/` directory is present but empty.

## Test Execution

**Commands:** Not configured (no `pytest.ini`, no `pyproject.toml` test config)

## Coverage Targets

**Current:** 0% (no tests)
**Goals:** Not documented
**Enforcement:** None

## Test Coverage Matrix

| Code Layer | Required Test Type | Location Pattern | Run Command |
|------------|-------------------|-----------------|------------|
| `audio_recorder.py` | unit | tests/ | pytest |
| `transcriber.py` | unit/integration (mock API) | tests/ | pytest |
| `audio_validator.py` | unit | tests/ | pytest |
| `database.py` | integration | tests/ | pytest |
| `network_monitor.py` | unit | tests/ | pytest |
| `agents/text_reviewer_agent.py` | unit (mock Groq) | tests/ | pytest |
| UI (main_window.py) | e2e / manual | tests/ | pytest + manual |

## Parallelism Assessment

| Test Type | Parallel-Safe? | Isolation Model | Evidence |
|-----------|---------------|----------------|----------|
| unit | Likely Yes | Per-test isolation if mocks used | No tests exist |
| integration | Unknown | Single SQLite file per process | No tests exist |
| e2e | N/A | Not implemented | No tests exist |

## Gate Check Commands

| Gate Level | When to Use | Command |
|------------|-------------|---------|
| Quick | After small changes | `pytest tests/ -x -q` |
| Full | After significant changes | `pytest tests/ -v` |
| Build | Pre-commit / CI | `black --check app/ && pytest tests/` |

## Notes

- `tests/` directory exists but is empty — no tests written yet
- No `pytest.ini` or test configuration in `pyproject.toml`
- Database uses a single file (`transcriber_data.db`) — parallel integration tests would need unique paths
- Consider adding tests for: audio_recorder RMS calculation, transcriber routing logic, database CRUD, audio validation thresholds
