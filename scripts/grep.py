#!/usr/bin/env python3

import argparse
import json
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

PROJECTS_DIR = Path.home() / ".claude" / "projects"


def search_session(file_path, keyword, max_matches):
    keyword_lower = keyword.lower()
    session_id = file_path.stem
    cwd = None
    matches = []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line)

                    if not cwd and "cwd" in data:
                        cwd = data["cwd"]

                    if data.get("type") not in ("user", "assistant"):
                        continue
                    msg = data.get("message", {})
                    content = msg.get("content", "")

                    if isinstance(content, list):
                        parts = []
                        for part in content:
                            if isinstance(part, dict) and part.get("type") == "text":
                                parts.append(part.get("text", ""))
                        content = "\n".join(parts)

                    if not isinstance(content, str) or not content.strip():
                        continue

                    if keyword_lower in content.lower():
                        role = data["type"]
                        snippet = content.strip().replace("\n", " ")
                        if len(snippet) > 200:
                            idx = snippet.lower().find(keyword_lower)
                            start = max(0, idx - 80)
                            end = min(len(snippet), idx + len(keyword) + 80)
                            snippet = ("..." if start > 0 else "") + snippet[start:end] + ("..." if end < len(snippet) else "")
                        matches.append((role, snippet))

                        if len(matches) >= max_matches:
                            break

                except (json.JSONDecodeError, KeyError):
                    continue
    except Exception:
        return None

    if not matches:
        return None

    return {
        "session_id": session_id,
        "cwd": cwd,
        "matches": matches,
        "mtime": file_path.stat().st_mtime,
    }


def main():
    parser = argparse.ArgumentParser(description="Search Claude session contents by keyword")
    parser.add_argument("keyword", help="Keyword to search for")
    parser.add_argument("-n", "--limit", type=int, default=10, help="Max sessions to show (default: 10)")
    parser.add_argument("-m", "--max-matches", type=int, default=3, help="Max matches per session (default: 3)")
    parser.add_argument("--path", type=str, help="Projects directory path")
    args = parser.parse_args()

    project_dir = Path(args.path) if args.path else PROJECTS_DIR

    if not project_dir.exists():
        print(f"Error: {project_dir} not found", file=sys.stderr)
        return 1

    jsonl_files = list(project_dir.rglob("*.jsonl"))

    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(search_session, f, args.keyword, args.max_matches): f
            for f in jsonl_files
        }
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)

    results.sort(key=lambda x: x["mtime"], reverse=True)
    results = results[: args.limit]

    if not results:
        print(f'No sessions found matching "{args.keyword}"')
        return 0

    print(f'=== Sessions matching "{args.keyword}" ===')
    print()

    home = str(Path.home())
    for i, r in enumerate(results, 1):
        cwd_display = r["cwd"].replace(home, "~") if r["cwd"] and r["cwd"].startswith(home) else (r["cwd"] or "unknown")
        print(f"[{i}] {cwd_display}")
        if r["cwd"]:
            print(f"    cd {cwd_display} && claude --resume {r['session_id']}")
        else:
            print(f"    claude --resume {r['session_id']}")
        for role, snippet in r["matches"]:
            prefix = "❯" if role == "user" else " "
            print(f"    {prefix} {snippet}")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
