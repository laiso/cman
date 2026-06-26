# Development

This file is for maintainers and coding agents working on cman itself.
User-facing installation and usage stay in `README.md`.

## Architecture

```text
Natural language          Skills (UX)              MCP Server               Scripts (data)
                    ┌─────────────────┐      ┌─────────────────────┐  ┌────────────────┐
"What did I do      │ remember        │─────▶│ list_sessions       │──│ sessions.py    │
 yesterday?"     ──▶│ (auto-trigger)  │─────▶│ list_plans          │──│ plans.py       │
                    ├─────────────────┤─────▶│ list_memory         │──│ memory.py      │
/cm-status       ──▶│ cm-status       │─────▶│ search_sessions     │──│ grep.py        │
/remember …      ──▶│ remember        │─────▶│ list_pi_sessions    │──│ pi_sessions.py │
                    │                 │─────▶│ search_pi_sessions  │──│ pi_sessions.py │
                    │                 │─────▶│ search_all          │──│ search_all.py  │
                    └─────────────────┘      └─────────────────────┘  └────────────────┘
```

Claude Code uses `server.py` as an MCP server over stdio. The server reuses the
Python scripts that read Claude Code sessions, plans, memory files, and Pi
sessions directly.

Pi Coding Agent uses the package extension in `pi/extensions/index.js`. The
extension exposes native Pi tools and calls the same Python scripts.

## Local Development

Claude Code plugin testing:

```bash
claude --plugin-dir /path/to/cman
```

Pi package install from the working tree:

```bash
pi install . --local --approve
```

Load only the working-tree Pi extension:

```bash
PI_OFFLINE=1 pi --no-extensions -e ./pi/extensions/index.js --verbose --no-session
```

If `python3` is not available:

```bash
CMAN_PYTHON=python PI_OFFLINE=1 pi --no-extensions -e ./pi/extensions/index.js --verbose --no-session
```

## Validation

```bash
python3 -m py_compile server.py scripts/*.py
uv run --with pytest python -m pytest
python3 scripts/smoke.py
node --check pi/extensions/index.js
```

Optional Pi E2E:

```bash
python3 scripts/smoke.py --pi-e2e
```

`scripts/smoke.py` uses synthetic fixture data. It sets `CMAN_CLAUDE_DIR` and
`CMAN_PI_SESSIONS_DIR` to temporary directories so tests do not read real local
conversation logs.

## Pi Extension Debugging

Run a non-interactive synthetic-log check:

```bash
tmpdir=$(mktemp -d /tmp/cman-pi-ext.XXXXXX)
mkdir -p "$tmpdir/sessions/--tmp-cman--"
cat > "$tmpdir/sessions/--tmp-cman--/2026-06-26T00-00-00-000Z_test.jsonl" <<'JSONL'
{"type":"session","version":3,"id":"pi-extension-test","timestamp":"2026-06-26T00:00:00.000Z","cwd":"/tmp/cman"}
{"type":"message","id":"u1","parentId":null,"timestamp":"2026-06-26T00:00:01.000Z","message":{"role":"user","content":[{"type":"text","text":"cman extension synthetic pi log"}]}}
JSONL

CMAN_PI_SESSIONS_DIR="$tmpdir/sessions" PI_OFFLINE=1 \
  pi --no-extensions -e ./pi/extensions/index.js --verbose --no-session \
  --tools cman_pi_sessions \
  -p 'Use the cman_pi_sessions tool with query synthetic and limit 1. Output only the tool result.'
```

Run cross-agent search from Pi:

```bash
CMAN_CLAUDE_DIR="$tmpdir/.claude" CMAN_PI_SESSIONS_DIR="$tmpdir/sessions" PI_OFFLINE=1 \
  pi --no-extensions -e ./pi/extensions/index.js --verbose --no-session \
  --tools cman_search_all \
  -p 'Use the cman_search_all tool with query synthetic and limit 5. Output only the tool result.'
```

## Compatibility Notes

Skills allow both Claude Code plugin MCP tool names and project MCP tool names:

- `mcp__plugin_cman_cman__*` when cman is loaded via `claude --plugin-dir .`
- `mcp__cman__*` when the included `.mcp.json` is loaded directly as a project MCP server

The plugin path is the intended installation path. Direct `.mcp.json` loading is
kept for local development and compatibility smoke coverage, not as the README
installation path.

## Safety Controls

- Generated resume commands quote path and ID tokens to avoid copy-paste command injection.
- Titles, snippets, memory previews, and `cat` output strip terminal/control sequences.
- MCP, CLI, and Pi extension path overrides are limited to expected roots by default.
- Set `CMAN_ALLOW_ARBITRARY_PATH=1` only for explicit local debugging.
- Recursive JSONL scans are bounded by `CMAN_MAX_SCAN_FILES`, defaulting to 20000.
