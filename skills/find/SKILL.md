---
name: find
description: Search across all Claude Code sessions, plans, and memory files by keyword. Finds past work and provides resume commands. Use when looking for a specific past conversation or feature.
argument-hint: <keyword>
allowed-tools: Bash
disable-model-invocation: true
---

# Cross-Search

Search sessions, plans, and memory for a keyword.

## Data

### Sessions
!`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/cc-sessions.py -n 100`

### Plans
!`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/cc-plans.py`

### Memory
!`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/cc-memory.py`

## Instructions

1. The search keyword is: `$ARGUMENTS`
2. Filter all three data sources for entries containing the keyword (case-insensitive).
3. Present matches grouped by type:

### Output format

```
## Search Results for "{keyword}"

### Sessions
- [{title}] — {relative_time} — `claude --resume {id}`

### Plans
- [{plan_title}] — {N} sessions
  `open {plan_path}`

### Memory
- [{scope}] {file_path}

No matches found in {type}.
```

- If the keyword is empty or missing, ask the user what they want to search for.
- Highlight the most relevant matches first.
- Always include the resume command for matching sessions.
