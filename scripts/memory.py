#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path


def find_claude_md_files():
    """Find all CLAUDE.md files at different scopes"""
    files = []

    # Managed policy (organization-wide)
    managed_paths = [
        Path("/Library/Application Support/ClaudeCode/CLAUDE.md"),
        Path("/etc/claude-code/CLAUDE.md"),
        Path("C:/Program Files/ClaudeCode/CLAUDE.md"),
    ]
    for p in managed_paths:
        if p.exists():
            files.append(("managed", p))

    # User-level
    user_claude_md = Path.home() / ".claude" / "CLAUDE.md"
    if user_claude_md.exists():
        files.append(("user", user_claude_md))

    # User rules
    user_rules_dir = Path.home() / ".claude" / "rules"
    if user_rules_dir.exists():
        for f in user_rules_dir.rglob("*.md"):
            files.append(("user-rules", f))

    # Project-level (current directory)
    cwd = Path.cwd()
    project_claude_md = cwd / "CLAUDE.md"
    if project_claude_md.exists():
        files.append(("project", project_claude_md))

    project_claude_dir = cwd / ".claude" / "CLAUDE.md"
    if project_claude_dir.exists():
        files.append(("project", project_claude_dir))

    # Project rules
    project_rules_dir = cwd / ".claude" / "rules"
    if project_rules_dir.exists():
        for f in project_rules_dir.rglob("*.md"):
            files.append(("project-rules", f))

    # Auto memory
    memory_dir = Path.home() / ".claude" / "projects"
    if memory_dir.exists():
        for proj_dir in sorted(
            memory_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True
        ):
            memory_md = proj_dir / "memory" / "MEMORY.md"
            if memory_md.exists():
                files.append(("auto-memory", memory_md))

            # Other memory files
            memory_files_dir = proj_dir / "memory"
            if memory_files_dir.exists():
                for f in memory_files_dir.glob("*.md"):
                    if f.name != "MEMORY.md":
                        files.append(("auto-memory", f))

    return files


def get_file_preview(file_path: Path, lines: int = 5) -> str:
    """Get first N lines of file as preview"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            preview = []
            for i, line in enumerate(f):
                if i >= lines:
                    break
                preview.append(line.rstrip())
            return "\n".join(preview)
    except Exception:
        return "(unable to read)"


def format_path(path: Path) -> str:
    """Format path with ~ for home directory"""
    home = str(Path.home())
    return str(path).replace(home, "~", 1) if str(path).startswith(home) else str(path)


def main():
    parser = argparse.ArgumentParser(description="View and manage Claude memory files")
    parser.add_argument("-c", "--cat", action="store_true", help="Display file content")
    parser.add_argument(
        "-n", "--lines", type=int, default=5, help="Number of lines to preview"
    )
    parser.add_argument("pattern", nargs="?", help="Filter files by pattern")
    args = parser.parse_args()

    files = find_claude_md_files()

    if args.pattern:
        files = [
            (scope, f) for scope, f in files if args.pattern.lower() in str(f).lower()
        ]

    if not files:
        print("No memory files found")
        return 0

    scope_order = {
        "managed": 0,
        "user": 1,
        "user-rules": 2,
        "project": 3,
        "project-rules": 4,
        "auto-memory": 5,
    }
    files.sort(key=lambda x: (scope_order.get(x[0], 99), str(x[1])))

    if args.cat:
        if len(files) == 1:
            file_path = files[0][1]
            with open(file_path, "r", encoding="utf-8") as f:
                print(f.read())
        else:
            print("Multiple files found. Specify a pattern to select one:")
            for scope, f in files:
                print(f"  {format_path(f)}")
            return 1
        return 0

    print("=== Claude Memory Files ===")
    print()

    current_scope = None
    for scope, file_path in files:
        if scope != current_scope:
            print(f"## {scope}")
            current_scope = scope

        preview = get_file_preview(file_path, args.lines)
        print(f"\n### {format_path(file_path)}")
        for line in preview.split("\n"):
            print(f"  {line}")

    print()
    print("Usage:")
    print("  cc-memory -c        # Display content")
    print("  cc-memory pattern   # Filter by pattern")

    return 0


if __name__ == "__main__":
    sys.exit(main())
