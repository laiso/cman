#!/usr/bin/env python3

import argparse
import json
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

PROJECTS_DIR = Path.home() / ".claude" / "projects"

# Relevance weights by message role
_ROLE_WEIGHT = {"user": 3, "summary": 3, "assistant": 1}


def _tokenize_query(keyword):
    """Split query into lower-cased tokens for order-independent AND matching."""
    return [t.lower() for t in keyword.split() if t]


def _all_tokens_match(tokens, text_lower):
    """Return True when every token appears somewhere in *text_lower*."""
    return all(t in text_lower for t in tokens)


def _extract_snippet(content, tokens, max_len=200, context=80):
    """Return a short snippet centred on the first matching token."""
    snippet = content.strip().replace("\n", " ")
    if len(snippet) <= max_len:
        return snippet
    snippet_lower = snippet.lower()
    best_idx = len(snippet_lower)
    best_token_len = 0
    for t in tokens:
        idx = snippet_lower.find(t)
        if idx != -1 and (idx < best_idx or (idx == best_idx and len(t) > best_token_len)):
            best_idx = idx
            best_token_len = len(t)
    if best_idx >= len(snippet_lower):
        best_idx = 0
        best_token_len = 0
    start = max(0, best_idx - context)
    end = min(len(snippet), best_idx + best_token_len + context)
    return ("..." if start > 0 else "") + snippet[start:end] + ("..." if end < len(snippet) else "")


def search_session(file_path, keyword, max_matches):
    tokens = _tokenize_query(keyword)
    if not tokens:
        return None
    session_id = file_path.stem
    cwd = None
    matches = []
    score = 0.0

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line)

                    if not cwd and "cwd" in data:
                        cwd = data["cwd"]

                    role = data.get("type")
                    if role not in ("user", "assistant", "summary"):
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

                    content_lower = content.lower()
                    if _all_tokens_match(tokens, content_lower):
                        weight = _ROLE_WEIGHT.get(role, 1)
                        score += weight
                        if len(matches) < max_matches:
                            snippet = _extract_snippet(content, tokens)
                            matches.append((role, snippet))

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
        "score": score,
        "mtime": file_path.stat().st_mtime,
    }


def search_memory_files(keyword, memory_files=None):
    """Search memory (.md) file bodies for *keyword* tokens.

    *memory_files* is an iterable of ``(scope, Path)`` tuples (same format
    returned by ``memory.find_claude_md_files``).  Returns a list of dicts
    with keys ``scope``, ``path``, ``snippet``, and ``score``.
    """
    if memory_files is None:
        return []
    tokens = _tokenize_query(keyword)
    if not tokens:
        return []
    results = []
    for scope, file_path in memory_files:
        try:
            text = file_path.read_text(encoding="utf-8")
        except Exception:
            continue
        if not _all_tokens_match(tokens, text.lower()):
            continue
        snippet = _extract_snippet(text, tokens, max_len=200, context=80)
        results.append({
            "scope": scope,
            "path": str(file_path),
            "snippet": snippet,
            "score": 1.0,
        })
    return results


def main():
    parser = argparse.ArgumentParser(description="Search Claude session contents by keyword")
    parser.add_argument("keyword", help="Keyword (or multi-word query) to search for")
    parser.add_argument("-n", "--limit", type=int, default=20, help="Max sessions to show (default: 20)")
    parser.add_argument("-m", "--max-matches", type=int, default=3, help="Max matches per session (default: 3)")
    parser.add_argument("--offset", type=int, default=0, help="Skip first N results for pagination (default: 0)")
    parser.add_argument("--path", type=str, help="Projects directory path")
    parser.add_argument("--exclude-subagents", action="store_true", help="Exclude agent-* session files")
    args = parser.parse_args()

    project_dir = Path(args.path) if args.path else PROJECTS_DIR

    if not project_dir.exists():
        print(f"Error: {project_dir} not found", file=sys.stderr)
        return 1

    jsonl_files = list(project_dir.rglob("*.jsonl"))
    if args.exclude_subagents:
        jsonl_files = [f for f in jsonl_files if not f.stem.startswith("agent-")]

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

    # Primary sort by relevance score (desc), secondary by mtime (desc)
    results.sort(key=lambda x: (x["score"], x["mtime"]), reverse=True)
    results = results[args.offset : args.offset + args.limit]

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
            import shlex
            needs_quote = "~" not in cwd_display
            quoted_cwd = shlex.quote(cwd_display) if needs_quote else cwd_display
            print(f"    cd {quoted_cwd} && claude --resume {r['session_id']}")
        else:
            print(f"    claude --resume {r['session_id']}")
        for role, snippet in r["matches"]:
            prefix = "❯" if role == "user" else " "
            print(f"    {prefix} {snippet}")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
