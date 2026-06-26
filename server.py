# /// script
# dependencies = ["mcp>=1.0"]
# ///

"""cman MCP server — exposes session/plan/memory tools for Claude Code."""

import io
import argparse
import shlex
import sys
from pathlib import Path

# Allow importing from scripts/
sys.path.insert(0, str(Path(__file__).parent / "scripts"))

from grep import search_session, search_memory_files, PROJECTS_DIR as GREP_PROJECTS_DIR
from sessions import list_sessions as _list_sessions
from plans import process_file as _process_plan_file, PROJECTS_DIR as PLANS_PROJECTS_DIR
from memory import find_claude_md_files, get_file_preview, format_path
from pi_sessions import list_pi_sessions as _list_pi_sessions, search_pi_session
from pi_sessions import _sanitize_text as _sanitize_pi_text
from search_all import search_all as _search_all
from sanitize import display_path, shell_cd_command, resume_command, strip_unsafe_terminal
from path_guard import ensure_allowed_path
from scan import iter_jsonl_files

from concurrent.futures import ThreadPoolExecutor, as_completed


def _home() -> str:
    return str(Path.home())


def list_sessions(
    limit: int = 50,
    exclude_subagents: bool = False,
    path: str | None = None,
    since: str | None = None,
) -> str:
    """List recent Claude Code sessions with metadata including title, time, size, and resume commands."""
    safe_limit = max(1, min(100, int(limit)))
    project_dir = ensure_allowed_path(path, [GREP_PROJECTS_DIR], "path") if path else None
    sessions = _list_sessions(
        project_dir,
        safe_limit,
        exclude_subagents=exclude_subagents,
        since=since,
    )

    if not sessions:
        return "No sessions found"

    home = _home()
    lines = ["=== Claude Sessions ===", ""]

    for i, s in enumerate(sessions, 1):
        lines.append(f"[{i}] {strip_unsafe_terminal(s['title'])}")
        lines.append(f"    {s['relative_time']} · {s['size']}")
        if s["cwd"]:
            lines.append(f"    {shell_cd_command(s['cwd'], 'claude', '--resume', s['session_id'])}")
        else:
            lines.append(f"    {resume_command('claude', '--resume', s['session_id'])}")
        lines.append("")

    if len(sessions) < safe_limit:
        lines.append(f"Total: {len(sessions)} sessions")

    return "\n".join(lines)


def list_plans(plans_dir: str | None = None) -> str:
    """List Claude Code plans with linked sessions and resume commands."""
    default_plans = Path.home() / ".claude" / "plans"
    pd = ensure_allowed_path(plans_dir, [default_plans], "plans_dir") if plans_dir else default_plans

    if not PLANS_PROJECTS_DIR.exists():
        return f"Error: {PLANS_PROJECTS_DIR} not found"
    if not pd.exists():
        return "No plans found"

    jsonl_files = list(iter_jsonl_files(PLANS_PROJECTS_DIR))

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
        lines.append(f"[{i}] {strip_unsafe_terminal(title)}")
        lines.append(f"    open {shlex.quote(strip_unsafe_terminal(plan_file_path))}")
        for session_id, cwd, _ in sessions:
            if cwd:
                lines.append(f"    {shell_cd_command(cwd, 'claude', '--resume', session_id)}")
            else:
                lines.append(f"    {resume_command('claude', '--resume', session_id)}")
        lines.append("")

    return "\n".join(lines)


def list_memory(pattern: str | None = None, cat: bool = False, lines: int = 5, cwd: str | None = None) -> str:
    """Discover and preview Claude memory files across all scopes (managed, user, project, auto-memory)."""
    safe_lines = max(0, min(50, int(lines)))
    files = find_claude_md_files(cwd)

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
                return strip_unsafe_terminal(f.read())
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
        preview = get_file_preview(file_path, safe_lines)
        out.append(f"\n### {format_path(file_path)}")
        for line in preview.split("\n"):
            out.append(f"  {strip_unsafe_terminal(line)}")

    return "\n".join(out)


def search_sessions(
    keyword: str,
    limit: int = 20,
    max_matches: int = 3,
    offset: int = 0,
    exclude_subagents: bool = False,
    include_memory: bool = False,
    include_history: bool = False,
    path: str | None = None,
) -> str:
    """Full-text search across Claude Code session contents by keyword.

    Multi-word queries use order-independent AND matching (all tokens must
    appear).  Results are ranked by relevance score, then by recency.

    Set *include_memory* to also search memory file bodies.
    Set *include_history* to also search ``~/.claude/history.jsonl``.
      Note: history.jsonl may contain inputs from all projects — use with care.
    Set *exclude_subagents* to skip ``agent-*`` session files.
    Use *offset* for pagination (skip first N results).
    """
    safe_limit = max(1, min(100, int(limit)))
    safe_matches = max(1, min(20, int(max_matches)))
    project_dir = ensure_allowed_path(path, [GREP_PROJECTS_DIR], "path") if path else GREP_PROJECTS_DIR

    if not project_dir.exists():
        return f"Error: {project_dir} not found"

    jsonl_files = list(iter_jsonl_files(project_dir))
    if exclude_subagents:
        jsonl_files = [f for f in jsonl_files if not f.stem.startswith("agent-")]

    if include_history:
        history_file = Path.home() / ".claude" / "history.jsonl"
        if history_file.exists():
            jsonl_files.append(history_file)

    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(search_session, f, keyword, safe_matches): f
            for f in jsonl_files
        }
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)

    # Primary sort by relevance score (desc), secondary by mtime (desc)
    results.sort(key=lambda x: (x["score"], x["mtime"]), reverse=True)
    safe_offset = max(0, offset)
    results = results[safe_offset : safe_offset + safe_limit]

    if not results and not include_memory:
        return f'No sessions found matching "{keyword}"'

    lines: list[str] = []

    if results:
        lines += [f'=== Sessions matching "{keyword}" ===', ""]
        for i, r in enumerate(results, 1):
            cwd_display = display_path(r["cwd"]) if r["cwd"] else "unknown"
            sid = r["session_id"]
            lines.append(f"[{i}] {cwd_display}")
            # history.jsonl has stem "history" which is not a resumable session
            is_resumable = sid != "history"
            if r["cwd"] and is_resumable:
                lines.append(f"    {shell_cd_command(r['cwd'], 'claude', '--resume', sid)}")
            elif is_resumable:
                lines.append(f"    {resume_command('claude', '--resume', sid)}")
            else:
                lines.append(f"    (from ~/.claude/history.jsonl)")
            for role, snippet in r["matches"]:
                if role == "user":
                    prefix = "❯"
                elif role == "summary":
                    prefix = "·"
                elif role == "system":
                    prefix = "%"
                else:
                    prefix = " "
                lines.append(f"    {prefix} {strip_unsafe_terminal(snippet)}")
            lines.append("")

    if include_memory:
        mem_files = find_claude_md_files()
        mem_results = search_memory_files(keyword, mem_files)
        if mem_results:
            lines += [f'=== Memory files matching "{keyword}" ===', ""]
            for j, mr in enumerate(mem_results, 1):
                mem_display_path = format_path(Path(mr["path"]))
                lines.append(f"[{j}] [{mr['scope']}] {mem_display_path}")
                lines.append(f"    {strip_unsafe_terminal(mr['snippet'])}")
                lines.append("")

    if not lines:
        return f'No results found matching "{keyword}"'

    return "\n".join(lines)


def list_pi_sessions(limit: int = 50, path: str | None = None, since: str | None = None) -> str:
    """List recent Pi Coding Agent sessions with metadata and resume commands."""
    from pi_sessions import pi_sessions_dir

    safe_limit = max(1, min(100, int(limit)))
    session_dir = ensure_allowed_path(path, [pi_sessions_dir()], "path") if path else None

    try:
        sessions = _list_pi_sessions(session_dir, safe_limit, since=since)
    except FileNotFoundError as e:
        if path is None:
            return "No Pi sessions found"
        return f"Error: {e}"

    if not sessions:
        return "No Pi sessions found"

    home = _home()
    lines = ["=== Pi Sessions ===", ""]

    for i, s in enumerate(sessions, 1):
        lines.append(f"[{i}] {strip_unsafe_terminal(s['title'])}")
        lines.append(f"    {s['relative_time']} · {s['size']}")
        if s["cwd"]:
            lines.append(
                f"    {shell_cd_command(s['cwd'], 'pi', '--session', s['session_id'])}"
            )
        else:
            lines.append(f"    {resume_command('pi', '--session', s['session_id'])}")
        lines.append("")

    if len(sessions) < safe_limit:
        lines.append(f"Total: {len(sessions)} sessions")

    return "\n".join(lines)


def search_pi_sessions(
    keyword: str,
    limit: int = 20,
    max_matches: int = 3,
    offset: int = 0,
    path: str | None = None,
) -> str:
    """Full-text search across Pi Coding Agent session contents by keyword."""
    from pi_sessions import pi_sessions_dir

    safe_limit = max(1, min(100, int(limit)))
    safe_matches = max(1, min(20, int(max_matches)))
    session_dir = ensure_allowed_path(path, [pi_sessions_dir()], "path") if path else pi_sessions_dir()

    if not session_dir.exists():
        if path is None:
            return f'No Pi sessions found matching "{keyword}"'
        return f"Error: {session_dir} not found"

    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(search_pi_session, f, keyword, safe_matches): f
            for f in iter_jsonl_files(session_dir)
        }
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)

    results.sort(key=lambda x: (x["score"], x["mtime"]), reverse=True)
    safe_offset = max(0, offset)
    results = results[safe_offset : safe_offset + safe_limit]

    if not results:
        return f'No Pi sessions found matching "{keyword}"'

    lines = [f'=== Pi Sessions matching "{keyword}" ===', ""]
    for i, result in enumerate(results, 1):
        cwd_display = display_path(result["cwd"]) if result["cwd"] else "unknown"
        lines.append(f"[{i}] {cwd_display}")
        if result["cwd"]:
            lines.append(
                f"    {shell_cd_command(result['cwd'], 'pi', '--session', result['session_id'])}"
            )
        else:
            lines.append(f"    {resume_command('pi', '--session', result['session_id'])}")
        for role, snippet in result["matches"]:
            prefix = "❯" if role == "user" else " "
            lines.append(f"    {prefix} {_sanitize_pi_text(snippet)}")
        lines.append("")

    return "\n".join(lines)


def search_all(
    keyword: str,
    limit: int = 20,
    max_matches: int = 3,
    include_memory: bool = True,
    claude_path: str | None = None,
    pi_path: str | None = None,
    source: str = "all",
) -> str:
    """Cross-search Claude Code sessions, Pi sessions, and memory files."""
    return _search_all(
        keyword,
        limit=max(1, min(100, int(limit))),
        max_matches=max(1, min(20, int(max_matches))),
        include_memory=include_memory,
        claude_path=str(ensure_allowed_path(claude_path, [GREP_PROJECTS_DIR], "claude_path")) if claude_path else None,
        pi_path=str(ensure_allowed_path(pi_path, [__import__('pi_sessions').pi_sessions_dir()], "pi_path")) if pi_path else None,
        source=source,
    )


def run_smoke() -> int:
    checks = [
        ("sessions", list_sessions(limit=5, exclude_subagents=True), "Claude Sessions"),
        ("plans", list_plans(), ("Claude Code Plans", "No plans found")),
        ("memory", list_memory(), "Claude Memory Files"),
        ("search", search_sessions("cman", limit=5), "matching"),
        ("pi sessions", list_pi_sessions(limit=5), ("Pi Sessions", "No Pi sessions found")),
        ("pi search", search_pi_sessions("cman", limit=5), ("Pi Sessions matching", "No Pi sessions found")),
        ("cross search", search_all("cman", limit=5), "Cross-agent memory matching"),
    ]
    for name, output, expected in checks:
        expected_values = expected if isinstance(expected, tuple) else (expected,)
        if not any(value in output for value in expected_values):
            print(f"{name}: expected one of {expected_values!r}", file=sys.stderr)
            print(output, file=sys.stderr)
            return 1
        print(f"ok mcp {name}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run cman MCP server")
    parser.add_argument("--smoke", action="store_true", help="Run server tool smoke checks")
    args = parser.parse_args()

    if args.smoke:
        return run_smoke()

    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("cman")
    mcp.tool()(list_sessions)
    mcp.tool()(list_plans)
    mcp.tool()(list_memory)
    mcp.tool()(search_sessions)
    mcp.tool()(list_pi_sessions)
    mcp.tool()(search_pi_sessions)
    mcp.tool()(search_all)
    mcp.run(transport="stdio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
