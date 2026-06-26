"""Tests for scripts/pi_sessions.py."""

import json
import tempfile
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
