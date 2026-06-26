---
name: cm-status
description: Show current coding-agent activity. By default shows current project only. Use "all" to see all projects.
argument-hint: [all]
allowed-tools: mcp__plugin_cman_cman__*
---

# Status

Show an overview of current Claude Code and Pi Coding Agent activity.

## Instructions

First, gather data by calling these tools in parallel:
1. `mcp__plugin_cman_cman__list_plans`
2. `mcp__plugin_cman_cman__list_sessions` with limit=10 and exclude_subagents=true
3. `mcp__plugin_cman_cman__list_memory`
4. `mcp__plugin_cman_cman__list_pi_sessions` with limit=10

Then use the results to generate the output.

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
| # | Agent | Title | Project | When | CLI Resume |
|---|-------|-------|---------|------|------------|
| 1 | Claude | {title} | {project} | {relative_time} | `cd {cwd} && claude --resume {session_id}` |
| 2 | Pi | {title} | {project} | {relative_time} | `cd {cwd} && pi --session {path}` |

### Memory Overview
- {project}: {count} files
  - `{full_path_to_file_1}`
  - `{full_path_to_file_2}`
```

- Keep it scannable — tables for plans and sessions, bullet list for memory.
- For the "Project" column, extract the last directory component from the `cd` path.
- If there are no active plans, say "No active plans" instead of an empty table.
- For the CLI Resume column: use the exact resume command shown by the MCP tool. For Claude sessions this is `claude --resume`; for Pi sessions this is `pi --session`.
- For the Title column, rephrase raw prompts into brief work descriptions (e.g., "@README.md" → "README editing", "/remember test" → "Search testing").
- For Memory Overview, always include the full file path (e.g., `~/.claude/projects/-Users-.../memory/filename.md`) for each file listed in the data.
