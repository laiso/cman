#!/usr/bin/env python3

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed


def get_relative_time(mtime: float) -> str:
    now = datetime.now().timestamp()
    diff = now - mtime

    if diff < 60:
        return f"{int(diff)} seconds ago"
    elif diff < 3600:
        return f"{int(diff / 60)} minutes ago"
    elif diff < 86400:
        return f"{int(diff / 3600)} hours ago"
    elif diff < 604800:
        return f"{int(diff / 86400)} days ago"
    else:
        return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")


def get_first_message_title(file: Path) -> str:
    try:
        with open(file, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i > 50:
                    break
                try:
                    data = json.loads(line)
                    if data.get("type") == "user" and "message" in data:
                        content = data["message"].get("content", "")
                        if isinstance(content, str) and content.strip():
                            return content.split("\n")[0][:80]
                        elif isinstance(content, list):
                            for part in content:
                                if (
                                    isinstance(part, dict)
                                    and part.get("type") == "text"
                                ):
                                    text = part.get("text", "").strip()
                                    if text:
                                        return text.split("\n")[0][:80]
                except (json.JSONDecodeError, KeyError):
                    continue
    except Exception:
        pass
    return "(no messages)"


def process_session(f: Path) -> dict:
    session_id = f.stem
    stat = f.stat()
    mtime = stat.st_mtime
    size = stat.st_size
    size_str = (
        f"{size / 1024 / 1024:.1f}MB" if size > 1024 * 1024 else f"{size / 1024:.1f}KB"
    )

    cwd = None
    with open(f, "r", encoding="utf-8") as file:
        for line in file:
            try:
                data = json.loads(line)
                if "cwd" in data:
                    cwd = data.get("cwd")
                    break
            except (json.JSONDecodeError, KeyError):
                continue

    title = get_first_message_title(f)

    return {
        "session_id": session_id,
        "cwd": cwd,
        "title": title,
        "mtime": mtime,
        "relative_time": get_relative_time(mtime),
        "size": size_str,
        "file": f,
    }


def list_sessions(project_dir: Path = None, limit: int = 50):
    if project_dir is None:
        project_dir = Path.home() / ".claude" / "projects"

    if not project_dir.exists():
        raise FileNotFoundError(f"Projects directory not found: {project_dir}")

    jsonl_files = list(project_dir.rglob("*.jsonl"))
    jsonl_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

    sessions = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_file = {
            executor.submit(process_session, f): f for f in jsonl_files
        }
        for future in as_completed(future_to_file):
            try:
                sessions.append(future.result())
            except Exception:
                pass

    sessions.sort(key=lambda x: x["mtime"], reverse=True)
    return sessions[:limit]


def main():
    parser = argparse.ArgumentParser(description="List Claude sessions")
    parser.add_argument(
        "-n", "--limit", type=int, default=50, help="Number of sessions to show"
    )
    parser.add_argument("--path", type=str, help="Projects directory path")
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="Show only session IDs"
    )
    args = parser.parse_args()

    project_dir = Path(args.path) if args.path else None

    try:
        sessions = list_sessions(project_dir, args.limit)

        if args.quiet:
            for s in sessions:
                print(s["session_id"])
            return 0

        print("=== Claude Sessions ===")
        print()

        for i, s in enumerate(sessions, 1):
            print(f"[{i}] {s['title']}")
            print(f"    {s['relative_time']} · {s['size']}")
            if s["cwd"]:
                print(f"    cd {s['cwd']} && claude --resume {s['session_id']}")
            else:
                print(f"    claude --resume {s['session_id']}")
            print()

        if not sessions:
            print("No sessions found")
            return 0

        if len(sessions) < args.limit:
            print(f"Total: {len(sessions)} sessions")

        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
