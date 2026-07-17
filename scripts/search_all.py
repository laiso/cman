#!/usr/bin/env python3

"""Cross-search Claude Code, Pi, Codex, and memory files."""

import argparse
import os
import shlex
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from grep import search_memory_files, search_session
from memory import find_claude_md_files, format_path
from pi_sessions import pi_sessions_dir, search_pi_session
from pi_sessions import _display_path as _display_pi_path
from pi_sessions import _sanitize_text
from codex_sessions import codex_session_dirs, iter_codex_session_files, search_codex_session
from sanitize import display_path as _safe_display_path
from sanitize import shell_cd_command, resume_command, strip_unsafe_terminal
from scan import iter_jsonl_files
from path_guard import ensure_allowed_path


def _home() -> str:
    return os.environ.get("HOME", str(Path.home()))


def _display_path(value: str | Path | None) -> str:
    if not value:
        return "unknown"
    text = str(value)
    home = _home()
    return _safe_display_path(text, home)


def _claude_projects_dir() -> Path:
    claude_dir = Path(os.environ.get("CMAN_CLAUDE_DIR", Path.home() / ".claude"))
    return Path(os.environ.get("CMAN_CLAUDE_PROJECTS_DIR", claude_dir / "projects"))


def _search_claude(keyword: str, max_matches: int, path: Path | None):
    project_dir = path or _claude_projects_dir()
    if not project_dir.exists():
        return []

    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(search_session, file_path, keyword, max_matches): file_path
            for file_path in iter_jsonl_files(project_dir)
            if not file_path.stem.startswith("agent-")
        }
        for future in as_completed(futures):
            result = future.result()
            if result:
                result["source"] = "claude"
                results.append(result)
    return results


def _search_pi(keyword: str, max_matches: int, path: Path | None):
    session_dir = path or pi_sessions_dir()
    if not session_dir.exists():
        return []

    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(search_pi_session, file_path, keyword, max_matches): file_path
            for file_path in iter_jsonl_files(session_dir)
        }
        for future in as_completed(futures):
            result = future.result()
            if result:
                result["source"] = "pi"
                results.append(result)
    return results


def _search_codex(keyword: str, max_matches: int, path: Path | None):
    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(search_codex_session, file_path, keyword, max_matches): file_path
            for file_path in iter_codex_session_files(path)
        }
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)
    return results


def _search_memory(keyword: str):
    results = []
    for result in search_memory_files(keyword, find_claude_md_files()):
        results.append({
            "source": "memory",
            "session_id": None,
            "cwd": None,
            "matches": [(result["scope"], result["snippet"])],
            "score": result["score"],
            "mtime": Path(result["path"]).stat().st_mtime,
            "path": result["path"],
        })
    return results


def _format_result(index: int, result: dict) -> list[str]:
    source = result["source"]
    lines: list[str] = []

    if source == "claude":
        cwd_display = _display_path(result.get("cwd"))
        lines.append(f"[{index}] Claude {cwd_display}")
        if result.get("cwd"):
            lines.append(f"    {shell_cd_command(result['cwd'], 'claude', '--resume', result['session_id'])}")
        else:
            lines.append(f"    {resume_command('claude', '--resume', result['session_id'])}")
    elif source == "pi":
        cwd_display = _display_pi_path(result.get("cwd"))
        lines.append(f"[{index}] Pi {cwd_display}")
        if result.get("cwd"):
            lines.append(f"    {shell_cd_command(result['cwd'], 'pi', '--session', result['session_id'])}")
        else:
            lines.append(f"    {resume_command('pi', '--session', result['session_id'])}")
    elif source == "codex":
        cwd_display = _display_path(result.get("cwd"))
        lines.append(f"[{index}] Codex {cwd_display}")
        if result.get("cwd"):
            lines.append(f"    {shell_cd_command(result['cwd'], 'codex', 'resume', result['session_id'])}")
        else:
            lines.append(f"    {resume_command('codex', 'resume', result['session_id'])}")
    else:
        display_path = _display_path(result["path"])
        lines.append(f"[{index}] Memory {display_path}")

    for role, snippet in result["matches"]:
        if source == "claude":
            prefix = "❯" if role == "user" else " "
            lines.append(f"    {prefix} {_sanitize_text(snippet)}")
        elif source in {"pi", "codex"}:
            prefix = "❯" if role == "user" else " "
            lines.append(f"    {prefix} {strip_unsafe_terminal(snippet)}")
        else:
            lines.append(f"    [{role}] {_sanitize_text(snippet)}")

    return lines


def search_all(
    keyword: str,
    limit: int = 20,
    max_matches: int = 3,
    include_memory: bool = True,
    claude_path: str | None = None,
    pi_path: str | None = None,
    codex_path: str | None = None,
    source: str = "all",
) -> str:
    if source not in {"all", "claude", "pi", "codex", "memory"}:
        raise ValueError(f"Unknown source: {source}")

    results = []
    if source in {"all", "claude"}:
        results.extend(_search_claude(keyword, max_matches, Path(claude_path) if claude_path else None))
    if source in {"all", "pi"}:
        results.extend(_search_pi(keyword, max_matches, Path(pi_path) if pi_path else None))
    if source in {"all", "codex"}:
        results.extend(_search_codex(keyword, max_matches, Path(codex_path) if codex_path else None))
    if include_memory and source in {"all", "memory"}:
        results.extend(_search_memory(keyword))

    results.sort(key=lambda x: (x["score"], x["mtime"]), reverse=True)
    results = results[: max(0, limit)]

    if not results:
        return f'No {source} results found matching "{keyword}"'

    label = "Cross-agent memory" if source == "all" else f"{source.title()} memory"
    lines = [f'=== {label} matching "{keyword}" ===', ""]
    for index, result in enumerate(results, 1):
        lines.extend(_format_result(index, result))
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Cross-search cman memory across coding agents")
    parser.add_argument("keyword", help="Keyword or multi-word query to search for")
    parser.add_argument("-n", "--limit", type=int, default=20, help="Max results to show")
    parser.add_argument("-m", "--max-matches", type=int, default=3, help="Max matches per result")
    parser.add_argument("--no-memory", action="store_true", help="Skip Claude memory files")
    parser.add_argument("--claude-path", help="Override Claude projects directory")
    parser.add_argument("--pi-path", help="Override Pi sessions directory")
    parser.add_argument("--codex-path", help="Override Codex sessions directory")
    parser.add_argument(
        "--source",
        choices=("all", "claude", "pi", "codex", "memory"),
        default="all",
        help="Restrict search to one source. Default: all",
    )
    args = parser.parse_args()

    print(search_all(
        args.keyword,
        limit=args.limit,
        max_matches=args.max_matches,
        include_memory=not args.no_memory,
        claude_path=str(ensure_allowed_path(args.claude_path, [_claude_projects_dir()], "claude-path")) if args.claude_path else None,
        pi_path=str(ensure_allowed_path(args.pi_path, [pi_sessions_dir()], "pi-path")) if args.pi_path else None,
        codex_path=str(ensure_allowed_path(args.codex_path, codex_session_dirs(), "codex-path")) if args.codex_path else None,
        source=args.source,
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
