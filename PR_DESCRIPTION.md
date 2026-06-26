## Summary

- Adds Pi Coding Agent session support alongside the existing Claude Code data sources.
- Exposes Pi session listing and full-text search through MCP tools.
- Keeps the current Claude session, plan, and memory tools unchanged.

## Testing notes

`CMAN_CLAUDE_DIR` is a test isolation hook. In normal use cman reads `~/.claude`, but the smoke test must not depend on or expose the developer's real local Claude history. `scripts/smoke.py` creates a temporary synthetic `.claude` tree, sets `CMAN_CLAUDE_DIR` to that directory, and then runs the CLI scripts plus `server.py --smoke` against only that fixture data.

Pi uses the same pattern through `CMAN_PI_SESSIONS_DIR`: the smoke test writes a synthetic Pi JSONL session under a temporary `.pi/agent/sessions` tree and points cman at it. This verifies list/search behavior without touching real `~/.pi` logs.

## Validation

- `python3 -m py_compile server.py scripts/*.py`
- `uv run --with pytest python -m pytest`
- `python3 scripts/smoke.py`
- `python3 scripts/smoke.py --claude-e2e`
