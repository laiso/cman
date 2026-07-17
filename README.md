# cman

Agentic memory for coding agents.

cman searches your existing Claude Code, Pi Coding Agent, and Codex logs. It does not
need an external database, API key, or extra storage.

## Install

Claude Code:

```bash
/plugin marketplace add laiso/cman
/plugin install cman@cman
```

Codex:

```bash
codex plugin marketplace add laiso/cman
codex plugin add cman@cman
```

Pi Coding Agent:

```bash
pi install git:https://github.com/laiso/cman.git --approve
```

## Use

Ask naturally:

```text
What did I do today?
What did I work on last week?
Where was that auth-related work?
```

Useful commands:

| Command | Purpose |
| --- | --- |
| `$remember ...` (Codex) or `/remember ...` (Claude) | Search and summarize Claude Code, Pi, Codex, and memory logs |
| `/cm-status` | Show recent sessions, plans, and memory status |

When you do not name a specific agent, cman searches across Claude Code, Pi,
Codex, and memory files together. Sub-agent session logs are excluded.

## Requirements

- [uv](https://docs.astral.sh/uv/) for the Claude Code and Codex MCP server
- Python 3 for the Pi extension scripts

For Pi, cman uses the first working interpreter from `CMAN_PYTHON`, `PYTHON`,
`python3`, then `python`.

## License

MIT
