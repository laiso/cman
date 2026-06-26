#!/usr/bin/env python3

"""List and search Pi Coding Agent session JSONL files."""

import argparse
import json
import os
import shlex
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from grep import _all_tokens_match, _extract_snippet, _tokenize_query
from sessions import get_relative_time


def pi_agent_dir() -> Path:
    return Path(os.environ.get("CMAN_PI_AGENT_DIR", Path.home() / ".pi" / "agent"))


def pi_sessions_dir() -> Path:
    return Path(os.environ.get("CMAN_PI_SESSIONS_DIR", pi_agent_dir() / "sessions"))


_ROLE_WEIGHT = {"user": 3, "assistant": 1, "toolResult": 1}


def _content_to_text(content, include_thinking: bool = False) -> str:
    parts: list[str] = []

    if isinstance(content, str):
        return content

    if isinstance(content, dict):
        content = [content]

    if not isinstance(content, list):
        return ""

    for part in content:
        if not isinstance(part, dict):
            continue
        part_type = part.get("type")
        if part_type == "text":
            text = part.get("text", "")
            if isinstance(text, str):
                parts.append(text)
        elif part_type == "toolCall":
            name = part.get("name", "")
            arguments = part.get("arguments", {})
            if isinstance(arguments, (dict, list)):
                arg_text = json.dumps(arguments, ensure_ascii=False)
            else:
                arg_text = str(arguments)
            parts.append(f"{name} {arg_text}".strip())
        elif part_type == "thinking" and include_thinking:
            text = part.get("text", "")
            if isinstance(text, str):
                parts.append(text)

    return "\n".join(p for p in parts if p)


def _collect_searchable_text(data):
    if data.get("type") != "message":
        return None, ""

    message = data.get("message", {})
    if not isinstance(message, dict):
        return None, ""

    role = message.get("role")
    if role not in _ROLE_WEIGHT:
        return None, ""

    text = _content_to_text(message.get("content", ""))
    if not text.strip():
        return None, ""

    return role, text


def _read_header(file_path: Path) -> dict:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if data.get("type") == "session":
                    return data
                return data if "cwd" in data else {}
    except Exception:
        return {}
    return {}


def _first_user_title(file_path: Path) -> str:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i > 80:
                    break
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if data.get("type") != "message":
                    continue
                message = data.get("message", {})
                if not isinstance(message, dict) or message.get("role") != "user":
                    continue
                text = _content_to_text(message.get("content", "")).strip()
                if text:
                    return text.split("\n")[0][:80]
    except Exception:
        pass
    return "(no messages)"


def process_pi_session(file_path: Path) -> dict:
    stat = file_path.stat()
    header = _read_header(file_path)
    session_id = header.get("id") or file_path.stem
    size = stat.st_size
    size_str = (
        f"{size / 1024 / 1024:.1f}MB" if size > 1024 * 1024 else f"{size / 1024:.1f}KB"
    )

    return {
        "source": "pi",
        "session_id": session_id,
        "cwd": header.get("cwd"),
        "title": _first_user_title(file_path),
        "mtime": stat.st_mtime,
        "relative_time": get_relative_time(stat.st_mtime),
        "size": size_str,
        "file": file_path,
    }


def list_pi_sessions(session_dir: Path = None, limit: int = 50):
    if session_dir is None:
        session_dir = pi_sessions_dir()

    if not session_dir.exists():
        raise FileNotFoundError(f"Pi sessions directory not found: {session_dir}")

    jsonl_files = list(session_dir.rglob("*.jsonl"))
    jsonl_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

    sessions = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_file = {executor.submit(process_pi_session, f): f for f in jsonl_files}
        for future in as_completed(future_to_file):
            try:
                sessions.append(future.result())
            except Exception:
                pass

    sessions.sort(key=lambda x: x["mtime"], reverse=True)
    return sessions[:limit]


def search_pi_session(file_path: Path, keyword: str, max_matches: int):
    tokens = _tokenize_query(keyword)
    if not tokens:
        return None

    header = _read_header(file_path)
    session_id = header.get("id") or file_path.stem
    cwd = header.get("cwd")
    matches = []
    score = 0.0

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if not cwd and isinstance(data.get("cwd"), str):
                    cwd = data.get("cwd")

                role, text = _collect_searchable_text(data)
                if not role or not _all_tokens_match(tokens, text.lower()):
                    continue

                score += _ROLE_WEIGHT.get(role, 1)
                if len(matches) < max_matches:
                    matches.append((role, _extract_snippet(text, tokens)))
    except Exception:
        return None

    if not matches:
        return None

    return {
        "source": "pi",
        "session_id": session_id,
        "cwd": cwd,
        "file": file_path,
        "matches": matches,
        "score": score,
        "mtime": file_path.stat().st_mtime,
    }


def main():
    parser = argparse.ArgumentParser(description="List or search Pi Coding Agent sessions")
    parser.add_argument("keyword", nargs="?", help="Keyword (or multi-word query) to search for")
    parser.add_argument("-n", "--limit", type=int, default=50, help="Number of sessions to show")
    parser.add_argument("-m", "--max-matches", type=int, default=3, help="Max matches per session")
    parser.add_argument("--path", type=str, help="Pi sessions directory path")
    args = parser.parse_args()

    session_dir = Path(args.path) if args.path else None

    try:
        if args.keyword:
            search_dir = session_dir or pi_sessions_dir()
            if not search_dir.exists():
                print(f"Error: {search_dir} not found", file=sys.stderr)
                return 1
            results = []
            for file_path in search_dir.rglob("*.jsonl"):
                result = search_pi_session(file_path, args.keyword, args.max_matches)
                if result:
                    results.append(result)
            results.sort(key=lambda x: (x["score"], x["mtime"]), reverse=True)
            results = results[: args.limit]
            if not results:
                print(f'No Pi sessions found matching "{args.keyword}"')
                return 0
            print(f'=== Pi Sessions matching "{args.keyword}" ===')
            print()
            for i, result in enumerate(results, 1):
                print(f"[{i}] {result['cwd'] or 'unknown'}")
                print(f"    pi --session {shlex.quote(str(result['file']))}")
                for role, snippet in result["matches"]:
                    prefix = ">" if role == "user" else " "
                    print(f"    {prefix} {snippet}")
                print()
            return 0

        sessions = list_pi_sessions(session_dir, args.limit)
        print("=== Pi Sessions ===")
        print()
        for i, session in enumerate(sessions, 1):
            print(f"[{i}] {session['title']}")
            print(f"    {session['relative_time']} · {session['size']}")
            print(f"    pi --session {shlex.quote(str(session['file']))}")
            print()
        if not sessions:
            print("No sessions found")
        elif len(sessions) < args.limit:
            print(f"Total: {len(sessions)} sessions")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
