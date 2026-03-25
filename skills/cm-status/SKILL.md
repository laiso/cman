---
name: cm-status
description: Show current Claude Code activity. By default shows current project only. Use "all" to see all projects.
argument-hint: [all]
allowed-tools: Bash(python*)
disable-model-invocation: true
---

# Status

Show an overview of current Claude Code activity.

## Data

### Plans
!`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/plans.py`

### Recent Sessions
!`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sessions.py -n 10`

### Memory
!`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/memory.py`

## Instructions

Use the data in the Data section above to generate the output.

### Scope

- Default: Show only entries matching the current working directory.
- If `$ARGUMENTS` contains `all`: Show entries from all projects.

To determine the current project, use the last component of the current working directory.
Filter plans, sessions, and memory by matching the project/cwd path.

### Output format

```
## Status

### Active Plans
| # | Plan | Sessions | Project |
|---|------|----------|---------|
| 1 | {title} | {count} | {project} |

### Recent Sessions
| # | Title | Project | When | Resume |
|---|-------|---------|------|--------|
| 1 | {title} | {project} | {relative_time} | `claude --resume {session_id}` |

### Memory Overview
- {project}: {count} files
  - `{full_path_to_file_1}`
  - `{full_path_to_file_2}`
```

- Keep it scannable — tables for plans and sessions, bullet list for memory.
- For the "Project" column, extract the last directory component from the `cd` path.
- If there are no active plans, say "No active plans" instead of an empty table.
- ALWAYS include the session ID in the Resume column. The session ID is shown in the data (e.g., `claude --resume 7bb6cc10-aa5f-427e-a257-6ae1176748dd`). Never omit it.
- For the Title column, rephrase raw prompts into brief work descriptions (e.g., "@README.md" → "README editing", "cman:search test" → "Search testing").
- For Memory Overview, always include the full file path (e.g., `~/.claude/projects/-Users-.../memory/filename.md`) for each file listed in the data.
