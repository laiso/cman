#!/usr/bin/env python3

import argparse
import json
import sys
from pathlib import Path


def find_session_file(session_id: str) -> Path:
    projects_dir = Path.home() / ".claude" / "projects"
    if not projects_dir.exists():
        raise FileNotFoundError(f"Projects directory not found: {projects_dir}")

    session_file = projects_dir / f"{session_id}.jsonl"
    if session_file.exists():
        return session_file

    for f in projects_dir.rglob(f"{session_id}.jsonl"):
        return f

    raise FileNotFoundError(f"Session not found: {session_id}")


def export_conversation(session_id: str, output_file: str = None) -> str:
    session_file = find_session_file(session_id)

    messages = []
    with open(session_file, "r", encoding="utf-8") as f:
        for line in f:
            try:
                data = json.loads(line)

                if data.get("type") == "user" and "message" in data:
                    msg = data["message"]
                    content = msg.get("content", "")
                    if isinstance(content, list):
                        text_parts = []
                        for part in content:
                            if isinstance(part, dict) and part.get("type") == "text":
                                text_parts.append(part.get("text", ""))
                        content = "\n".join(text_parts)
                    if content.strip():
                        messages.append(("user", content))

                elif data.get("type") == "assistant" and "message" in data:
                    msg = data["message"]
                    content = msg.get("content", "")
                    if isinstance(content, list):
                        text_parts = []
                        for part in content:
                            if isinstance(part, dict) and part.get("type") == "text":
                                text_parts.append(part.get("text", ""))
                        content = "\n".join(text_parts)
                    if content.strip():
                        messages.append(("assistant", content))

            except json.JSONDecodeError:
                continue

    if not messages:
        raise RuntimeError("No messages found in this session")

    filename = output_file or f"{session_id}.txt"
    with open(filename, "w", encoding="utf-8") as f:
        for role, content in messages:
            if role == "user":
                f.write(f"❯ {content}\n\n")
            else:
                f.write(f"{content}\n\n")

    return filename


def main():
    parser = argparse.ArgumentParser(description="Export Claude conversation to file")
    parser.add_argument("session_id", help="Session ID to export")
    parser.add_argument(
        "-o", "--output", help="Output filename (default: <session_id>.txt)"
    )
    args = parser.parse_args()

    print(f"Exporting session {args.session_id}...")
    try:
        filename = export_conversation(args.session_id, args.output)
        print(f"Exported to: {filename}")
        return 0
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
