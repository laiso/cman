---
name: recap
description: Summarize recent Claude Code work sessions. Generates a daily or weekly recap of what was accomplished across projects. Use for standups, weekly reports, or remembering where you left off.
argument-hint: [daily|weekly]
allowed-tools: Bash
disable-model-invocation: true
---

# Work Recap

Generate a summary of recent Claude Code sessions.

## Data

!`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/cc-sessions.py -n 50`

## Instructions

1. If `$ARGUMENTS` is `weekly`, filter to sessions from the past 7 days. Otherwise default to `daily` (past 24 hours).
2. Group sessions by project (based on the `cd` path shown in each entry).
3. Present the recap in this format:

### Output format

```
## Work Recap — {period}

### Completed
- **{project}**: {summary from session title}
- **{project}**: {summary from session title}

### In Progress
- **{project}**: {summary} — `claude --resume {id}`

### Stats
- {N} sessions across {M} projects
```

- Use the session title (first line of each entry) to infer what was done.
- Sessions from more than a few hours ago with no follow-up are likely "completed".
- Very recent sessions are likely "in progress" — include resume commands for these.
- If no sessions match the time period, say so clearly.
