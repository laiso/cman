#!/usr/bin/env python3

import json
import os
import shlex
from sanitize import shell_cd_command, resume_command, strip_unsafe_terminal
from scan import iter_jsonl_files
from path_guard import ensure_allowed_path
import sys
from pathlib import Path


def claude_dir() -> Path:
    return Path(os.environ.get("CMAN_CLAUDE_DIR", Path.home() / ".claude"))


PROJECTS_DIR = Path(os.environ.get("CMAN_CLAUDE_PROJECTS_DIR", claude_dir() / "projects"))


def process_file(file_path, plans_dir):
    session_id = Path(file_path).stem
    slug = None
    cwd = None

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    if not slug and "slug" in data:
                        slug = data["slug"]
                    if not cwd and "cwd" in data:
                        cwd = data["cwd"]
                    if slug and cwd:
                        break
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        print(f"Warning: Failed to read {file_path}: {e}", file=sys.stderr)
        return None

    if not slug:
        return None

    plan_file = plans_dir / f"{slug}.md"
    if not plan_file.exists():
        return None

    plan_file_path = str(plan_file)

    try:
        with open(plan_file, "r", encoding="utf-8") as f:
            title = strip_unsafe_terminal(f.readline().strip().lstrip("#").strip())
    except Exception as e:
        print(f"Warning: Failed to read {plan_file}: {e}", file=sys.stderr)
        return None

    mtime = file_path.stat().st_mtime

    return (slug, title, session_id, cwd, mtime, plan_file_path)


def main():
    default_plans_dir = Path(os.environ.get("CMAN_CLAUDE_PLANS_DIR", claude_dir() / "plans"))
    if len(sys.argv) > 1:
        plans_dir = ensure_allowed_path(sys.argv[1], [default_plans_dir], "plans_dir")
    else:
        plans_dir = default_plans_dir

    if not PROJECTS_DIR.exists():
        print(f"Error: {PROJECTS_DIR} not found", file=sys.stderr)
        return 1

    print("=== Claude Code Plans ===")
    print()

    if not plans_dir.exists():
        print("No sessions found")
        return 0

    jsonl_files = list(iter_jsonl_files(PROJECTS_DIR))

    results = []
    for f in jsonl_files:
        r = process_file(f, plans_dir)
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
        print("No sessions found")
        return 0

    home = str(Path.home())
    for i, (slug, (title, plan_file_path, sessions)) in enumerate(sorted_results, 1):
        print(f"[{i}] {title}")
        print(f"    open {shlex.quote(strip_unsafe_terminal(plan_file_path))}")
        for session_id, cwd, _ in sessions:
            if cwd:
                print(f"    {shell_cd_command(cwd, 'claude', '--resume', session_id)}")
            else:
                print(f"    {resume_command('claude', '--resume', session_id)}")
        print()

    return 0


if __name__ == "__main__":
    exit(main())
