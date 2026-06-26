# cman — Agentic Memory for Coding Agents

Your memory is already there. cman just searches it agentically.

No external database, no API keys, no extra storage. cman gives Claude search over your existing Claude Code sessions, plans, and memory files — and can also inspect Pi Coding Agent sessions.

## Installation

```bash
/plugin marketplace add laiso/cman
/plugin install cman@cman
```

For Pi Coding Agent, install the same checkout as a Pi package:

```bash
pi install . --local --approve
```

Or load the extension once without installing:

```bash
PI_OFFLINE=1 pi --no-extensions -e ./extensions/index.js --verbose --no-session
```

## How it works

Just ask Claude naturally:

```
> What did I do yesterday?
> What did I work on last week?
> Where was that auth-related work?
```

Claude automatically searches your sessions, plans, and memory files — then summarizes the results.

You can also use skills directly:

| Skill | Scope | Purpose |
|-------|-------|---------|
| `/remember` … | All projects | Search and summarize past sessions (e.g. `/remember FOO BAR` for keywords) |
| `/cm-status` | Current project | Quick overview of plans, sessions, and memory (`all` for everything) |

The **`remember`** skill is the primary search command (`/remember`). With the plugin enabled, the palette may show the namespaced form (e.g. `cman:remember`). Workflow text lives in [`skills/cm-search/SKILL.md`](skills/cm-search/SKILL.md) for now; the legacy **`cm-search`** skill name is **deprecated** and will be removed in a future release. **`cm-status`** may appear as `cman:cm-status` in the same way.

## Example output

### "What did I do yesterday?"

<details>
<summary>Show example</summary>

```
## Work Recap — Past 24 hours

### Completed
- **web-app**: User dashboard chart component
- **web-app**: Fixed pagination bug on /users endpoint
- **web-app**: PR review (add rate limiter, update deps)
- **infra**: Cluster upgrade plan drafted
- **mobile-app**: Build config cleanup

### In Progress
- **web-app**: CSV export feature — `claude --resume a2ac93f1...`
- **infra**: Cost analysis — `claude --resume 06365b61...`

### Stats
- 50 sessions across 4 projects
```

</details>

### "Where was that auth work?"

<details>
<summary>Show example</summary>

```
## Search Results for "auth"

### Plans
- [Kubernetes cluster upgrade] — 3 sessions
  (Contains service account and auth configuration)

### Memory
- [web-app] project_oauth_migration.md
  OAuth2 migration — moving from session-based auth to JWT tokens

### Conversation matches (deep search)
- [web-app] Permission settings investigation — 5 days ago
  `claude --resume a82548ab...`
```

</details>

### /cm-status

<details>
<summary>Show example</summary>

```
Status

Active Plans
┌───┬──────────────────────────────────────────┬──────────┬─────────┐
│ # │ Plan                                     │ Sessions │ Project │
├───┼──────────────────────────────────────────┼──────────┼─────────┤
│ 1 │ feat: Add user dashboard with charts     │ 12       │ web-app │
│ 2 │ CSV export → Google Sheets integration   │ 16       │ web-app │
│ 3 │ Kubernetes cluster upgrade               │ 3        │ infra   │
│ 4 │ Frontend i18n support                    │ 11       │ web-app │
└───┴──────────────────────────────────────────┴──────────┴─────────┘

Recent Sessions
┌───┬─────────────────────────┬─────────┬────────────────┬──────────────────────────────────────────────────┬─────────────────────────────┐
│ # │ Title                   │ Project │ When           │ CLI Resume                                       │ Interactive                 │
├───┼─────────────────────────┼─────────┼────────────────┼──────────────────────────────────────────────────┼─────────────────────────────┤
│ 1 │ README editing          │ web-app │ 10 seconds ago │ cd ~/work/web-app && claude --resume a1b2c3d4... │ /resume a1b2c3d4...         │
│ 2 │ Status skill testing    │ web-app │ 1 minutes ago  │ cd ~/work/web-app && claude --resume e5f6g7h8... │ /resume e5f6g7h8...         │
│ 3 │ Search skill testing    │ web-app │ 3 minutes ago  │ cd ~/work/web-app && claude --resume i9j0k1l2... │ /resume i9j0k1l2...         │
└───┴─────────────────────────┴─────────┴────────────────┴──────────────────────────────────────────────────┴─────────────────────────────┘

Memory Overview
- web-app: 3 files
  - ~/.claude/projects/.../web-app/memory/MEMORY.md
  - ~/.claude/projects/.../web-app/memory/project_design.md
  - ~/.claude/projects/.../web-app/memory/feedback_conventions.md
```

</details>

## Requirements

- [uv](https://docs.astral.sh/uv/) (Python package runner)

## Architecture

```
Natural language          Skills (UX)              MCP Server               Scripts (data)
                    ┌─────────────────┐      ┌─────────────────────┐  ┌────────────────┐
"What did I do      │ remember        │─────▶│ list_sessions       │──│ sessions.py    │
 yesterday?"     ──▶│ (auto-trigger)  │─────▶│ list_plans          │──│ plans.py       │
                    ├─────────────────┤─────▶│ list_memory         │──│ memory.py      │
/cm-status       ──▶│ cm-status       │─────▶│ search_sessions     │──│ grep.py        │
/remember …      ──▶│ remember        │─────▶│ list_pi_sessions    │──│ pi_sessions.py │
                    │                 │─────▶│ search_pi_sessions  │──│ pi_sessions.py │
                    └─────────────────┘      └─────────────────────┘  └────────────────┘
                    (workflow text: skills/cm-search/SKILL.md; cm-search skill deprecated)
```

Skills call MCP tools served by `server.py` (stdio transport, launched via `uv run --script`). The MCP server reuses logic from the Python scripts, which read `~/.claude/projects/**/*.jsonl`, memory files, and Pi sessions directly. Claude interprets, filters, and summarizes the output.

Pi Coding Agent support reads JSONL sessions from `~/.pi/agent/sessions/**/*.jsonl` through separate MCP tools (`list_pi_sessions`, `search_pi_sessions`) and `scripts/pi_sessions.py`.

## Development

```bash
# Local testing
claude --plugin-dir /path/to/cman

# CI-equivalent local checks
python3 -m py_compile server.py scripts/*.py
uv run --with pytest python -m pytest
python3 scripts/smoke.py
```

`scripts/smoke.py` uses synthetic fixture data. It sets `CMAN_CLAUDE_DIR` to a temporary `.claude` directory and `CMAN_PI_SESSIONS_DIR` to a temporary Pi sessions directory so tests never read real local conversation logs.

### Pi extension debugging

Load only the working-tree extension:

```bash
PI_OFFLINE=1 pi --no-extensions -e ./extensions/index.js --verbose --no-session
```

Run a non-interactive synthetic-log check:

```bash
tmpdir=$(mktemp -d /tmp/cman-pi-ext.XXXXXX)
mkdir -p "$tmpdir/sessions/--tmp-cman--"
cat > "$tmpdir/sessions/--tmp-cman--/2026-06-26T00-00-00-000Z_test.jsonl" <<'JSONL'
{"type":"session","version":3,"id":"pi-extension-test","timestamp":"2026-06-26T00:00:00.000Z","cwd":"/tmp/cman"}
{"type":"message","id":"u1","parentId":null,"timestamp":"2026-06-26T00:00:01.000Z","message":{"role":"user","content":[{"type":"text","text":"cman extension synthetic pi log"}]}}
JSONL

CMAN_PI_SESSIONS_DIR="$tmpdir/sessions" PI_OFFLINE=1 \
  pi --no-extensions -e ./extensions/index.js --verbose --no-session \
  --tools cman_pi_sessions \
  -p 'Use the cman_pi_sessions tool with query synthetic and limit 1. Output only the tool result.'
```

## License

MIT
