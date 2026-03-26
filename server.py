# /// script
# dependencies = ["mcp>=1.0"]
# ///

"""cman MCP server — exposes session/plan/memory tools for Claude Code."""

import io
import shlex
import sys
from pathlib import Path

# Allow importing from scripts/
sys.path.insert(0, str(Path(__file__).parent / "scripts"))

from mcp.server.fastmcp import FastMCP

from grep import search_session, PROJECTS_DIR as GREP_PROJECTS_DIR
from sessions import list_sessions as _list_sessions
from plans import process_file as _process_plan_file, PROJECTS_DIR as PLANS_PROJECTS_DIR
from memory import find_claude_md_files, get_file_preview, format_path

from concurrent.futures import ThreadPoolExecutor, as_completed

mcp = FastMCP("cman")


def _home() -> str:
    return str(Path.home())


@mcp.tool()
def list_sessions(limit: int = 50, exclude_subagents: bool = False, path: str | None = None) -> str:
    """List recent Claude Code sessions with metadata including title, time, size, and resume commands."""
    project_dir = Path(path) if path else None
    sessions = _list_sessions(project_dir, limit, exclude_subagents=exclude_subagents)

    if not sessions:
        return "No sessions found"

    home = _home()
    lines = ["=== Claude Sessions ===", ""]

    for i, s in enumerate(sessions, 1):
        lines.append(f"[{i}] {s['title']}")
        lines.append(f"    {s['relative_time']} · {s['size']}")
        if s["cwd"]:
            cwd = s["cwd"]
            display_cwd = cwd.replace(home, "~", 1) if cwd.startswith(home) else cwd
            needs_quote = "~" not in display_cwd
            quoted_cwd = shlex.quote(display_cwd) if needs_quote else display_cwd
            lines.append(f"    cd {quoted_cwd} && claude --resume {s['session_id']}")
        else:
            lines.append(f"    claude --resume {s['session_id']}")
        lines.append("")

    if len(sessions) < limit:
        lines.append(f"Total: {len(sessions)} sessions")

    return "\n".join(lines)


@mcp.tool()
def list_plans(plans_dir: str | None = None) -> str:
    """List Claude Code plans with linked sessions and resume commands."""
    pd = Path(plans_dir) if plans_dir else Path.home() / ".claude" / "plans"

    if not PLANS_PROJECTS_DIR.exists():
        return f"Error: {PLANS_PROJECTS_DIR} not found"
    if not pd.exists():
        return f"Error: {pd} not found"

    jsonl_files = list(PLANS_PROJECTS_DIR.rglob("*.jsonl"))

    results = []
    for f in jsonl_files:
        r = _process_plan_file(f, pd)
        if r:
            results.append(r)

    grouped = {}
    for slug, title, session_id, cwd, mtime, plan_file_path in results:
        if slug not in grouped:
            grouped[slug] = (title, plan_file_path, [])
        grouped[slug][2].append((session_id, cwd, mtime))

    sorted_results = sorted(grouped.items(), key=lambda x: x[0])
    for slug, (title, plan_file_path, sessions) in sorted_results:
        sessions.sort(key=lambda x: x[2], reverse=True)

    if not sorted_results:
        return "No plans found"

    home = _home()
    lines = ["=== Claude Code Plans ===", ""]

    for i, (slug, (title, plan_file_path, sessions)) in enumerate(sorted_results, 1):
        display_path = (
            plan_file_path.replace(home, "~", 1)
            if plan_file_path.startswith(home)
            else plan_file_path
        )
        lines.append(f"[{i}] {title}")
        lines.append(f"    open {display_path}")
        for session_id, cwd, _ in sessions:
            if cwd:
                display_cwd = cwd.replace(home, "~", 1) if cwd.startswith(home) else cwd
                needs_quote = "~" not in display_cwd
                lines.append(
                    f"    cd {shlex.quote(display_cwd) if needs_quote else display_cwd} && claude --resume {session_id}"
                )
            else:
                lines.append(f"    claude --resume {session_id}")
        lines.append("")

    return "\n".join(lines)


@mcp.tool()
def list_memory(pattern: str | None = None, cat: bool = False, lines: int = 5, cwd: str | None = None) -> str:
    """Discover and preview Claude memory files across all scopes (managed, user, project, auto-memory)."""
    import os

    # Temporarily change cwd if provided, for memory.py's Path.cwd() usage
    original_cwd = None
    if cwd:
        original_cwd = os.getcwd()
        try:
            os.chdir(cwd)
        except OSError:
            pass

    try:
        files = find_claude_md_files()
    finally:
        if original_cwd:
            os.chdir(original_cwd)

    if pattern:
        files = [
            (scope, f) for scope, f in files if pattern.lower() in str(f).lower()
        ]

    if not files:
        return "No memory files found"

    scope_order = {
        "managed": 0, "user": 1, "user-rules": 2,
        "project": 3, "project-rules": 4, "auto-memory": 5,
    }
    files.sort(key=lambda x: (scope_order.get(x[0], 99), str(x[1])))

    if cat:
        if len(files) == 1:
            file_path = files[0][1]
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        else:
            out = ["Multiple files found. Specify a pattern to select one:"]
            for scope, f in files:
                out.append(f"  {format_path(f)}")
            return "\n".join(out)

    out = ["=== Claude Memory Files ===", ""]
    current_scope = None
    for scope, file_path in files:
        if scope != current_scope:
            out.append(f"## {scope}")
            current_scope = scope
        preview = get_file_preview(file_path, lines)
        out.append(f"\n### {format_path(file_path)}")
        for line in preview.split("\n"):
            out.append(f"  {line}")

    return "\n".join(out)


@mcp.tool()
def search_sessions(keyword: str, limit: int = 10, max_matches: int = 3, path: str | None = None) -> str:
    """Full-text search across Claude Code session contents by keyword."""
    project_dir = Path(path) if path else GREP_PROJECTS_DIR

    if not project_dir.exists():
        return f"Error: {project_dir} not found"

    jsonl_files = list(project_dir.rglob("*.jsonl"))

    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(search_session, f, keyword, max_matches): f
            for f in jsonl_files
        }
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)

    results.sort(key=lambda x: x["mtime"], reverse=True)
    results = results[:limit]

    if not results:
        return f'No sessions found matching "{keyword}"'

    home = _home()
    lines = [f'=== Sessions matching "{keyword}" ===', ""]

    for i, r in enumerate(results, 1):
        cwd_display = r["cwd"].replace(home, "~") if r["cwd"] and r["cwd"].startswith(home) else (r["cwd"] or "unknown")
        lines.append(f"[{i}] {cwd_display}")
        if r["cwd"]:
            needs_quote = "~" not in cwd_display
            quoted_cwd = shlex.quote(cwd_display) if needs_quote else cwd_display
            lines.append(f"    cd {quoted_cwd} && claude --resume {r['session_id']}")
        else:
            lines.append(f"    claude --resume {r['session_id']}")
        for role, snippet in r["matches"]:
            prefix = "❯" if role == "user" else " "
            lines.append(f"    {prefix} {snippet}")
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run(transport="stdio")
