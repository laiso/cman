---
name: cm-search
description: "[Deprecated — use remember /remember instead; removal planned] Search and summarize past Claude Code work across all projects. Same workflow as remember; kept temporarily for compatibility."
argument-hint: [keywords...]
allowed-tools: mcp__plugin_cman_cman__*
---

# Search

> **Deprecation:** Prefer **`/remember`** ([remember skill](../remember/SKILL.md)). The **`cm-search`** skill name will be removed in a future release.

Search and summarize past Claude Code sessions, plans, and memory across all projects. The **remember** skill delegates here for the full instructions.

## Arguments

If `$ARGUMENTS` is non-empty (e.g. `/remember FOO BAR`), join the tokens into the search keyword and follow the **Search** flow. Do not ask the user to repeat the query.

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

### Search (e.g., "where was that auth work?", "find migration sessions", or keyword arguments after `/remember`)
1. Extract the keyword from the user's question, or from `$ARGUMENTS` when provided
2. First, search session titles, plans, and memory from the gathered data
3. Then ALWAYS run deep search: call `mcp__plugin_cman_cman__search_sessions` with the keyword
   - Use `include_memory=true` when the user may have stored relevant notes
   - Use `exclude_subagents=true` to skip sub-agent noise (default for targeted searches)
4. Combine results from both and present with resume commands
5. **Alternate spellings:** When searching for domain terms that may appear in different languages or spellings, run several `search_sessions` calls with alternate forms (e.g. English *and* Japanese: `Scan` / `スキャン`, or `DynamoDB` / `dynamo`) and merge the results

### General (e.g., "what was I working on?", "where did I leave off?")
1. Show the most recent sessions with context
2. Highlight anything that looks unfinished
3. Provide resume commands

Always include `claude --resume <id>` for sessions the user might want to continue.
Rephrase raw prompts into brief work descriptions (e.g., "@README.md" → "README editing").
