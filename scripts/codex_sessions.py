#!/usr/bin/env python3

"""List and search local Codex JSONL session logs."""

import argparse
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from grep import _all_tokens_match, _extract_snippet, _tokenize_query
from path_guard import ensure_allowed_path
from sanitize import display_path, shell_cd_command, resume_command, strip_unsafe_terminal
from scan import iter_jsonl_files
from sessions import get_relative_time, parse_since


_ROLE_WEIGHT = {"user": 3, "assistant": 1}
_INTERNAL_CONTEXT_RE = re.compile(
    r"<codex_internal_context\b[^>]*>.*?</codex_internal_context>",
    re.DOTALL,
)


def codex_dir() -> Path:
    return Path(
        os.environ.get(
            "CMAN_CODEX_DIR",
            os.environ.get("CODEX_HOME", Path.home() / ".codex"),
        )
    )


def codex_session_dirs() -> list[Path]:
    override = os.environ.get("CMAN_CODEX_SESSIONS_DIR")
    if override:
        return [Path(override)]
    root = codex_dir()
    return [root / "sessions", root / "archived_sessions"]


def iter_codex_session_files(path: Path | None = None):
    roots = [path] if path else codex_session_dirs()
    for root in roots:
        if root.exists():
            yield from iter_jsonl_files(root)


def _read_session_meta(file_path: Path) -> dict:
    try:
        with file_path.open("r", encoding="utf-8") as handle:
            for index, line in enumerate(handle):
                if index >= 40:
                    break
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("type") == "session_meta":
                    payload = row.get("payload", {})
                    return payload if isinstance(payload, dict) else {}
    except Exception:
        pass
    return {}


def _is_subagent_meta(meta: dict) -> bool:
    source = meta.get("source")
    thread_source = meta.get("thread_source")
    return (
        isinstance(source, dict) and "subagent" in source
    ) or (
        isinstance(thread_source, dict) and "subagent" in thread_source
    )


def is_codex_subagent(file_path: Path) -> bool:
    return _is_subagent_meta(_read_session_meta(file_path))


def _content_to_text(content) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""

    parts = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") not in {"input_text", "output_text", "text"}:
            continue
        text = item.get("text", "")
        if isinstance(text, str) and text:
            parts.append(text)
    return "\n".join(parts)


def _collect_searchable_text(row: dict):
    row_type = row.get("type")
    if row_type == "response_item":
        payload = row.get("payload", {})
    elif row_type == "message":
        # Older Codex rollout files stored message items at the top level.
        payload = row
    else:
        return None, ""
    if not isinstance(payload, dict) or payload.get("type") != "message":
        return None, ""
    role = payload.get("role")
    if role not in _ROLE_WEIGHT:
        return None, ""
    text = _content_to_text(payload.get("content", []))
    if role == "user":
        text = _INTERNAL_CONTEXT_RE.sub("", text)
    return (role, text) if text.strip() else (None, "")


def _session_identity(meta: dict, file_path: Path) -> tuple[str, str | None]:
    session_id = meta.get("id") or meta.get("session_id") or file_path.stem
    cwd = meta.get("cwd") if isinstance(meta.get("cwd"), str) else None
    return str(session_id), cwd


def search_codex_session(file_path: Path, keyword: str, max_matches: int):
    tokens = _tokenize_query(keyword)
    if not tokens:
        return None

    meta = _read_session_meta(file_path)
    if _is_subagent_meta(meta):
        return None

    session_id, cwd = _session_identity(meta, file_path)
    matches = []
    score = 0.0

    try:
        with file_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                role, text = _collect_searchable_text(row)
                if not role or not _all_tokens_match(tokens, text.lower()):
                    continue
                score += _ROLE_WEIGHT[role]
                if len(matches) < max_matches:
                    matches.append((role, _extract_snippet(text, tokens)))
    except Exception:
        return None

    if not matches:
        return None
    return {
        "source": "codex",
        "session_id": session_id,
        "cwd": cwd,
        "file": file_path,
        "matches": matches,
        "score": score,
        "mtime": file_path.stat().st_mtime,
    }


def _first_user_title(file_path: Path) -> str:
    try:
        with file_path.open("r", encoding="utf-8") as handle:
            for index, line in enumerate(handle):
                if index >= 200:
                    break
                try:
                    role, text = _collect_searchable_text(json.loads(line))
                except json.JSONDecodeError:
                    continue
                if role == "user" and text.strip():
                    return strip_unsafe_terminal(text.strip().splitlines()[0])[:80]
    except Exception:
        pass
    return "(no messages)"


def process_codex_session(file_path: Path) -> dict | None:
    meta = _read_session_meta(file_path)
    if _is_subagent_meta(meta):
        return None
    stat = file_path.stat()
    session_id, cwd = _session_identity(meta, file_path)
    size = stat.st_size
    size_text = f"{size / 1024 / 1024:.1f}MB" if size > 1024 * 1024 else f"{size / 1024:.1f}KB"
    return {
        "source": "codex",
        "session_id": session_id,
        "cwd": cwd,
        "title": _first_user_title(file_path),
        "mtime": stat.st_mtime,
        "relative_time": get_relative_time(stat.st_mtime),
        "size": size_text,
        "file": file_path,
    }


def list_codex_sessions(path: Path | None = None, limit: int = 50, since: str | None = None):
    files = list(iter_codex_session_files(path))
    since_ts = parse_since(since)
    if since_ts is not None:
        files = [item for item in files if item.stat().st_mtime >= since_ts]

    sessions = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(process_codex_session, item) for item in files]
        for future in as_completed(futures):
            try:
                result = future.result()
            except Exception:
                continue
            if result:
                sessions.append(result)
    sessions.sort(key=lambda item: item["mtime"], reverse=True)
    return sessions[:limit]


def main() -> int:
    parser = argparse.ArgumentParser(description="List or search local Codex sessions")
    parser.add_argument("keyword", nargs="?", help="Keyword or multi-word query")
    parser.add_argument("-n", "--limit", type=int, default=50)
    parser.add_argument("-m", "--max-matches", type=int, default=3)
    parser.add_argument("--since")
    parser.add_argument("--path")
    args = parser.parse_args()

    roots = codex_session_dirs()
    path = ensure_allowed_path(args.path, roots, "path") if args.path else None
    if args.keyword:
        results = []
        for file_path in iter_codex_session_files(path):
            result = search_codex_session(file_path, args.keyword, args.max_matches)
            if result:
                results.append(result)
        results.sort(key=lambda item: (item["score"], item["mtime"]), reverse=True)
        results = results[: max(0, args.limit)]
        if not results:
            print(f'No Codex sessions found matching "{args.keyword}"')
            return 0
        print(f'=== Codex Sessions matching "{args.keyword}" ===\n')
        for index, result in enumerate(results, 1):
            cwd = result.get("cwd")
            print(f"[{index}] {display_path(cwd) if cwd else 'unknown'}")
            if cwd:
                print(f"    {shell_cd_command(cwd, 'codex', 'resume', result['session_id'])}")
            else:
                print(f"    {resume_command('codex', 'resume', result['session_id'])}")
            for role, snippet in result["matches"]:
                print(f"    {'❯' if role == 'user' else ' '} {strip_unsafe_terminal(snippet)}")
            print()
        return 0

    sessions = list_codex_sessions(path, max(1, args.limit), args.since)
    if not sessions:
        print("No Codex sessions found")
        return 0
    print("=== Codex Sessions ===\n")
    for index, session in enumerate(sessions, 1):
        print(f"[{index}] {session['title']}")
        print(f"    {session['relative_time']} · {session['size']}")
        cwd = session.get("cwd")
        if cwd:
            print(f"    {shell_cd_command(cwd, 'codex', 'resume', session['session_id'])}")
        else:
            print(f"    {resume_command('codex', 'resume', session['session_id'])}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
