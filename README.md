# cman — Claude Code Session Manager Plugin

Browse, search, and summarize Claude Code sessions, plans, and memory across projects.

## Requirements

- Python 3 (standard library only, no pip install needed)

## Installation

```bash
# Local testing
claude --plugin-dir /path/to/cman

# Or install as a plugin
claude plugin add /path/to/cman
```

## Skills

### /cman:dash — Dashboard

Quick overview of current activity: active plans, recent sessions, memory status.

```
/cman:dash
```

### /cman:recap — Work Recap

Summarize what you've been working on. Useful for standups and daily review.

```
/cman:recap           # Past 24 hours (default)
/cman:recap weekly    # Past 7 days
```

### /cman:find — Cross-Search

Search across sessions, plans, and memory by keyword.

```
/cman:find auth       # Find sessions/plans/memory mentioning "auth"
/cman:find migration  # Find work related to migrations
```

### /cman:audit — Memory Audit

Analyze memory files for staleness, duplicates, bloat, and conflicts.

```
/cman:audit           # Audit all memory files
/cman:audit project   # Audit only project-scoped memory
```

## Architecture

```
Skills (UX layer)          Scripts (data layer)
┌────────────────┐         ┌────────────────┐
│ recap          │────────▶│ cc-sessions.py │
│ find           │────────▶│ cc-plans.py    │
│ dash           │────────▶│ cc-memory.py   │
│ audit          │────────▶│                │
└────────────────┘         └────────────────┘
```

Skills invoke Python scripts via dynamic context injection. Scripts read `~/.claude/projects/**/*.jsonl` and memory files directly. Claude interprets, filters, and summarizes the output.

## Standalone CLI

`cc-export.py` is available as a standalone CLI tool for exporting conversations:

```bash
python3 cc-export.py <session-id> [-o output.txt]
```
