---
name: remember
description: Search past coding-agent work across all projects. Use when the user invokes $remember or /remember with keywords, or asks about past sessions, recaps, or finding past work.
allowed-tools: mcp__plugin_cman_cman__*, mcp__cman__*
---

# Remember

Primary command: **`$remember`** in Codex or **`/remember`** in Claude Code (optional keywords as `$ARGUMENTS`).

Search and summarize past Claude Code, Pi Coding Agent, and Codex sessions, plans, and memory across all projects.

## Arguments

If `$ARGUMENTS` is non-empty (e.g. `/remember FOO BAR`), join the tokens into the search keyword and follow the **Search** flow. Do not ask the user to repeat the query.

## Instructions

First, gather data by calling these tools in parallel:
1. `mcp__plugin_cman_cman__list_sessions` with limit=200
2. `mcp__plugin_cman_cman__list_plans`
3. `mcp__plugin_cman_cman__list_memory`
4. `mcp__plugin_cman_cman__list_pi_sessions` with limit=200
5. `mcp__plugin_cman_cman__list_codex_sessions` with limit=200

When running inside Pi, use the native cman tools with the same intent:
1. `cman_search_all` for keyword search across all sources by default
2. `cman_claude_sessions` and `cman_pi_sessions` together for recent/date recaps; use `cman_search_all` for Codex history
3. A single source tool only when the user explicitly asks to limit the answer to that source

Then use the results to generate output. This skill searches across ALL projects by default. Determine what the user needs from context:

### Recap (e.g., "what did I do yesterday?", "weekly standup")
1. Filter sessions by time period (default: past 24 hours, "weekly" = past 7 days)
2. Group by project, summarize what was done
3. Show in-progress work with resume commands
4. Include session count and project stats
5. For date recaps such as "today" or "yesterday", use `list_sessions(since="today")` and `list_pi_sessions(since="today")` together, or in Pi use `cman_claude_sessions(since="today")` and `cman_pi_sessions(since="today")` together. Do not search for today's date as a keyword and do not inspect `~/.claude` or `~/.pi` with shell commands.
6. If the user explicitly asks to limit the answer to one source, only then use that source.

### Search (e.g., "where was that auth work?", "find migration sessions", or keyword arguments after `/remember`)
1. Extract the keyword from the user's question, or from `$ARGUMENTS` when provided
2. If the user did not explicitly name an agent/source, first call `mcp__plugin_cman_cman__search_all` (or `mcp__cman__search_all`) with the keyword
3. Then search session titles, plans, and memory from the gathered data
4. If the initial search has no useful results, retry conservative spelling or inflection variants (for example `updates` / `update`) before concluding there is no memory
5. If the user explicitly asks to limit the answer to one source, call only the matching source search (`search_sessions`, `search_pi_sessions`, `search_codex_sessions`, or `search_all` with `source=claude` / `source=pi` / `source=codex`), or call those tools when `search_all` needs more detail
   - Use `include_memory=true` when the user may have stored relevant notes
   - Sub-agent logs are excluded by cman automatically
6. Combine results from all matching agents and present with resume commands
7. **Alternate spellings:** When searching for domain terms that may appear in different languages or spellings, run several `search_all` / source-specific search calls with alternate forms (e.g. English *and* Japanese: `Scan` / `スキャン`, or `DynamoDB` / `dynamo`) and merge the results

### General (e.g., "what was I working on?", "where did I leave off?")
1. Show the most recent sessions with context
2. Highlight anything that looks unfinished
3. Provide resume commands

Always include the resume command shown by the tool (`claude --resume <id>`, `pi --session <id>`, or `codex resume <id>`) for sessions the user might want to continue.
Rephrase raw prompts into brief work descriptions (e.g., "@README.md" -> "README editing").
