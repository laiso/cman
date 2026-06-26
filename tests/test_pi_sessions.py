"""Tests for scripts/pi_sessions.py."""

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from pi_sessions import list_pi_sessions, process_pi_session, search_pi_session


def _write_pi_session(root: Path, name: str, rows: list[dict]) -> Path:
    session_dir = root / "--Users-kstg-work-laiso-cman--"
    session_dir.mkdir(parents=True, exist_ok=True)
    file_path = session_dir / name
    file_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )
    return file_path


def test_process_pi_session_uses_header_and_first_user_message():
    with tempfile.TemporaryDirectory() as td:
        file_path = _write_pi_session(Path(td), "2026-06-26T00-00-00Z_abc.jsonl", [
            {"type": "session", "id": "pi-session-id", "cwd": "/tmp/project"},
            {
                "type": "message",
                "message": {
                    "role": "user",
                    "content": [{"type": "text", "text": "Fix account issue\nwith details"}],
                },
            },
        ])

        session = process_pi_session(file_path)

        assert session["source"] == "pi"
        assert session["session_id"] == "pi-session-id"
        assert session["cwd"] == "/tmp/project"
        assert session["title"] == "Fix account issue"


def test_list_pi_sessions_finds_nested_jsonl_files():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write_pi_session(root, "2026-06-26T00-00-00Z_old.jsonl", [
            {"type": "session", "id": "old", "cwd": "/tmp/old"},
            {"type": "message", "message": {"role": "user", "content": "old cman"}},
        ])
        _write_pi_session(root, "2026-06-26T00-00-01Z_new.jsonl", [
            {"type": "session", "id": "new", "cwd": "/tmp/new"},
            {"type": "message", "message": {"role": "user", "content": "new cman"}},
        ])

        sessions = list_pi_sessions(root, limit=10)

        assert {s["session_id"] for s in sessions} == {"old", "new"}


def test_list_pi_sessions_filters_by_since_today():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        today = datetime.now().replace(hour=1, minute=0, second=0, microsecond=0)
        yesterday = today - timedelta(days=1)
        today_file = _write_pi_session(root, "2026-06-26T00-00-01Z_today.jsonl", [
            {"type": "session", "id": "today", "cwd": "/tmp/today"},
            {"type": "message", "message": {"role": "user", "content": "today cman"}},
        ])
        old_file = _write_pi_session(root, "2026-06-25T00-00-01Z_old.jsonl", [
            {"type": "session", "id": "old", "cwd": "/tmp/old"},
            {"type": "message", "message": {"role": "user", "content": "old cman"}},
        ])
        os.utime(today_file, (today.timestamp(), today.timestamp()))
        os.utime(old_file, (yesterday.timestamp(), yesterday.timestamp()))

        sessions = list_pi_sessions(root, limit=10, since="today")

        assert [session["session_id"] for session in sessions] == ["today"]


def test_search_pi_session_matches_text_and_tool_results_but_not_thinking():
    with tempfile.TemporaryDirectory() as td:
        file_path = _write_pi_session(Path(td), "2026-06-26T00-00-00Z_abc.jsonl", [
            {"type": "session", "id": "pi-session-id", "cwd": "/tmp/project"},
            {
                "type": "message",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "thinking", "text": "hidden-token"}],
                },
            },
            {
                "type": "message",
                "message": {
                    "role": "user",
                    "content": [{"type": "text", "text": "Investigate Pi cman session"}],
                },
            },
            {
                "type": "message",
                "message": {
                    "role": "toolResult",
                    "content": [{"type": "text", "text": "Pi cman tool output"}],
                },
            },
        ])

        result = search_pi_session(file_path, "Pi cman", max_matches=5)
        hidden = search_pi_session(file_path, "hidden-token", max_matches=5)

        assert result is not None
        assert result["session_id"] == "pi-session-id"
        assert len(result["matches"]) == 2
        assert result["score"] == 4.0
        assert hidden is None


def test_search_pi_session_sanitizes_home_paths_in_snippets(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        home = Path(td) / "home"
        monkeypatch.setenv("HOME", str(home))
        file_path = _write_pi_session(Path(td), "2026-06-26T00-00-00Z_abc.jsonl", [
            {"type": "session", "id": "pi-session-id", "cwd": str(home / "work" / "project")},
            {
                "type": "message",
                "message": {
                    "role": "user",
                    "content": f"Open {home}/work/project and run cman path test",
                },
            },
        ])

        result = search_pi_session(file_path, "cman path", max_matches=1)

        assert result is not None
        assert str(home) not in result["matches"][0][1]
        assert "~/work/project" in result["matches"][0][1]


def test_pi_sessions_cli_folds_home_paths_and_resumes_by_id(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        home = root / "home"
        sessions_dir = root / "sessions"
        file_path = _write_pi_session(sessions_dir, "2026-06-26T00-00-00Z_abc.jsonl", [
            {"type": "session", "id": "pi-session-id", "cwd": str(home / "work" / "project")},
            {
                "type": "message",
                "message": {
                    "role": "user",
                    "content": f"Open {home}/work/project and run cman path test",
                },
            },
        ])

        env = os.environ.copy()
        env["HOME"] = str(home)
        env["CMAN_PI_SESSIONS_DIR"] = str(sessions_dir)
        result = subprocess.run(
            [sys.executable, "scripts/pi_sessions.py", "cman path", "-n", "1"],
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

        assert str(home) not in result.stdout
        assert str(file_path) not in result.stdout
        assert "~/work/project" in result.stdout
        assert "pi --session pi-session-id" in result.stdout


def test_server_pi_tools_fold_home_paths_and_resume_by_id(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        home = root / "home"
        sessions_dir = root / "sessions"
        file_path = _write_pi_session(sessions_dir, "2026-06-26T00-00-00Z_abc.jsonl", [
            {"type": "session", "id": "pi-session-id", "cwd": str(home / "work" / "project")},
            {
                "type": "message",
                "message": {
                    "role": "user",
                    "content": f"Open {home}/work/project and run cman path test",
                },
            },
        ])

        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setenv("CMAN_PI_SESSIONS_DIR", str(sessions_dir))

        import server

        listed = server.list_pi_sessions(limit=1)
        searched = server.search_pi_sessions("cman path", limit=1)
        output = listed + "\n" + searched

        assert str(home) not in output
        assert str(file_path) not in output
        assert "cd ~/work/project && pi --session pi-session-id" in output
        assert "~/work/project" in output
