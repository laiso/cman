"""Tests for scripts/sessions.py."""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from sessions import get_first_message_title, list_sessions


def _write_session(path: Path, title: str, mtime: float):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join([
            json.dumps({"cwd": "/tmp/app"}),
            json.dumps({"type": "user", "message": {"content": title}}),
        ]) + "\n",
        encoding="utf-8",
    )
    path.touch()
    import os

    os.utime(path, (mtime, mtime))


def test_list_sessions_filters_by_since_today():
    with tempfile.TemporaryDirectory() as td:
        project_dir = Path(td)
        today = datetime.now().replace(hour=1, minute=0, second=0, microsecond=0)
        yesterday = today - timedelta(days=1)

        _write_session(project_dir / "today-session.jsonl", "today claude work", today.timestamp())
        _write_session(project_dir / "old-session.jsonl", "old claude work", yesterday.timestamp())

        sessions = list_sessions(project_dir, limit=10, since="today")

        assert [session["session_id"] for session in sessions] == ["today-session"]


def test_get_first_message_title_skips_claude_control_messages():
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "session.jsonl"
        path.write_text(
            "\n".join([
                json.dumps({"cwd": "/tmp/app"}),
                json.dumps({
                    "type": "user",
                    "message": {"content": "<command-message>cman:remember</command-message>"},
                }),
                json.dumps({
                    "type": "user",
                    "message": {"content": "<local-command-caveat>Caveat text</local-command-caveat>"},
                }),
                json.dumps({
                    "type": "user",
                    "message": {"content": "Design Pi extension support"},
                }),
            ]) + "\n",
            encoding="utf-8",
        )

        assert get_first_message_title(path) == "Design Pi extension support"
