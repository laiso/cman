---
name: search
description: Search and summarize past Claude Code work across all projects. Use when the user asks about past sessions, what they worked on yesterday or last week, where they left off, or is looking for a specific past conversation by keyword. Also handles daily/weekly recaps and standup summaries.
allowed-tools: Bash(python3 *)
---

# Search

Search and summarize past Claude Code sessions, plans, and memory across all projects.

## Data

### Sessions
!`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sessions.py -n 200`

### Plans
!`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/plans.py`

### Memory
!`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/memory.py`

## Instructions

Use the data in the Data section above to generate the output.

This skill searches across ALL projects by default. Determine what the user needs from context:

### Recap (e.g., "what did I do yesterday?", "weekly standup")
1. Filter sessions by time period (default: past 24 hours, "weekly" = past 7 days)
2. Group by project, summarize what was done
3. Show in-progress work with resume commands
4. Include session count and project stats

### Search (e.g., "where was that auth work?", "find migration sessions")
1. Extract the keyword from the user's question
2. First, search session titles, plans, and memory from the data above
3. Then ALWAYS run deep search to find matches in conversation contents:
   ```
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/grep.py <keyword> -n 10
   ```
4. Combine results from both and present with resume commands

### General (e.g., "what was I working on?", "where did I leave off?")
1. Show the most recent sessions with context
2. Highlight anything that looks unfinished
3. Provide resume commands

Always include `claude --resume <id>` for sessions the user might want to continue.
Rephrase raw prompts into brief work descriptions (e.g., "@README.md" → "README editing").

