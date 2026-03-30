---
name: remember
description: Search past Claude Code work across all projects. Primary skill — use when the user invokes /remember with keywords or asks about past sessions, recaps, or finding past work. Implementation is delegated to cm-search/SKILL.md until cm-search is removed.
argument-hint: [keywords...]
allowed-tools: mcp__plugin_cman_cman__*
---

# Remember

Primary slash command: **`/remember`** (optional keywords as `$ARGUMENTS`).

Follow the **Arguments** and **Instructions** in [`../cm-search/SKILL.md`](../cm-search/SKILL.md) exactly — that file is the single workflow definition until the legacy `cm-search` skill is dropped.

If the full text is not already in context, read `${CLAUDE_SKILL_DIR}/../cm-search/SKILL.md` before executing.
