---
name: dash
description: Show a dashboard of current Claude Code activity. Displays active plans, recent sessions, and memory status across all projects. Use for a quick overview of work in progress.
allowed-tools: Bash
disable-model-invocation: true
---

# Dashboard

Show an overview of current Claude Code activity.

## Data

### Plans
!`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/cc-plans.py`

### Recent Sessions
!`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/cc-sessions.py -n 10`

### Memory
!`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/cc-memory.py`

## Instructions

Present a concise dashboard combining all three data sources:

### Output format

```
## Dashboard

### Active Plans
| # | Plan | Sessions | Latest |
|---|------|----------|--------|
| 1 | {title} | {count} | {time} |

### Recent Sessions
| # | Title | Project | When |
|---|-------|---------|------|
| 1 | {title} | {project} | {relative_time} |

### Memory Overview
- {scope}: {count} files
```

- Keep it scannable — tables for plans and sessions, bullet list for memory.
- For the "Project" column, extract the last directory component from the `cd` path.
- If there are no active plans, say "No active plans" instead of an empty table.
- For sessions, the resume command is available via `claude --resume {id}` — mention this as a hint at the bottom.
