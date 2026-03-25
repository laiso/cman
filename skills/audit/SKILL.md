---
name: audit
description: Audit Claude Code memory files across all scopes and projects. Detects stale entries, duplicates, oversized files, and conflicting instructions. Use when cleaning up or reviewing memory.
argument-hint: [pattern]
allowed-tools: Bash, Read
disable-model-invocation: true
---

# Memory Audit

Analyze memory files and suggest cleanup actions.

## Data

!`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/cc-memory.py -c $ARGUMENTS`

## Instructions

1. Review each memory file from the output above.
2. For each file, check for these issues:

### Issue types

- **Stale references**: File paths or function names mentioned in memory that may no longer exist
- **Duplicates**: Same or very similar content across multiple project memories
- **Oversized**: MEMORY.md index files exceeding 200 lines (the truncation limit)
- **Conflicts**: Contradictory instructions across different scopes (e.g., user-level says "use tabs" but project says "use spaces")
- **Outdated dates**: References to dates or deadlines that have passed

3. If a pattern argument was provided, only audit files matching that pattern.
4. Use the Read tool to inspect specific memory files in detail if needed.

### Output format

```
## Memory Audit Report

### Issues Found

#### {file_path}
- **{issue_type}**: {description}
  **Action**: {suggested fix}

### Summary
- {N} files audited
- {M} issues found
- {K} files healthy
```

- Be specific about what to fix and how.
- If no issues are found, confirm the memory is healthy.
- Prioritize actionable issues over cosmetic ones.
