# cman

Agentic memory for coding agents.

cman searches your existing Claude Code and Pi Coding Agent logs. It does not
need an external database, API key, or extra storage.

## Install

Claude Code:

```bash
/plugin marketplace add laiso/cman
/plugin install cman@cman
```

Pi Coding Agent:

```bash
pi install . --local --approve
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
| `/remember ...` | Search and summarize past Claude Code, Pi, and memory logs |
| `/cm-status` | Show recent sessions, plans, and memory status |

When you do not name a specific agent, cman searches across Claude Code
sessions, Pi sessions, and memory files together.

## Requirements

- [uv](https://docs.astral.sh/uv/) for the Claude Code MCP server
- Python 3 for the Pi extension scripts

For Pi, cman uses the first working interpreter from `CMAN_PYTHON`, `PYTHON`,
`python3`, then `python`.

## License

MIT
