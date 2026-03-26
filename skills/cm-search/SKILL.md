---
name: cm-search
description: Search and summarize past Claude Code work across all projects. Use when the user asks about past sessions, what they worked on yesterday or last week, where they left off, or is looking for a specific past conversation by keyword. Also handles daily/weekly recaps and standup summaries.
allowed-tools: mcp__plugin_cman_cman__*
---

# Search

Search and summarize past Claude Code sessions, plans, and memory across all projects.

## Instructions

First, gather data by calling these tools in parallel:
1. `mcp__plugin_cman_cman__list_sessions` with limit=200
2. `mcp__plugin_cman_cman__list_plans`
3. `mcp__plugin_cman_cman__list_memory`

Then use the results to generate output. This skill searches across ALL projects by default. Determine what the user needs from context:

### Recap (e.g., "what did I do yesterday?", "weekly standup")
1. Filter sessions by time period (default: past 24 hours, "weekly" = past 7 days)
2. Group by project, summarize what was done
3. Show in-progress work with resume commands
4. Include session count and project stats

### Search (e.g., "where was that auth work?", "find migration sessions")
1. Extract the keyword from the user's question
2. First, search session titles, plans, and memory from the gathered data
3. Then ALWAYS run deep search: call `mcp__plugin_cman_cman__search_sessions` with the keyword
4. Combine results from both and present with resume commands

### General (e.g., "what was I working on?", "where did I leave off?")
1. Show the most recent sessions with context
2. Highlight anything that looks unfinished
3. Provide resume commands

Always include `claude --resume <id>` for sessions the user might want to continue.
Rephrase raw prompts into brief work descriptions (e.g., "@README.md" → "README editing").

