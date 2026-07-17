"""Tests for local Codex session discovery and search."""

import json
from pathlib import Path

from codex_sessions import list_codex_sessions, search_codex_session


def _write(path: Path, rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )
    return path


def _session_rows(session_id: str, cwd: str, text: str, source="cli"):
    return [
        {
            "type": "session_meta",
            "payload": {"id": session_id, "cwd": cwd, "source": source},
        },
        {
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": text}],
            },
        },
        {
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "Useful Codex memory result"}],
            },
        },
    ]


def test_search_codex_session_reads_messages(tmp_path):
    path = _write(
        tmp_path / "sessions" / "main.jsonl",
        _session_rows("codex-main", "/tmp/app", "Investigate cman updates"),
    )

    result = search_codex_session(path, "cman updates", 3)

    assert result is not None
    assert result["session_id"] == "codex-main"
    assert result["cwd"] == "/tmp/app"
    assert result["matches"][0][0] == "user"


def test_search_codex_session_excludes_subagents(tmp_path):
    path = _write(
        tmp_path / "sessions" / "subagent.jsonl",
        _session_rows(
            "codex-subagent",
            "/tmp/app",
            "Investigate cman updates",
            source={"subagent": "review"},
        ),
    )

    assert search_codex_session(path, "cman updates", 3) is None


def test_search_codex_session_supports_legacy_messages_and_ignores_internal_context(tmp_path):
    path = _write(
        tmp_path / "sessions" / "legacy.jsonl",
        [
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "legacy cman update"}],
            },
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "<codex_internal_context>secret marker</codex_internal_context>"}],
            },
        ],
    )

    assert search_codex_session(path, "legacy cman", 3) is not None
    assert search_codex_session(path, "secret marker", 3) is None


def test_list_codex_sessions_excludes_subagents(tmp_path, monkeypatch):
    sessions = tmp_path / ".codex" / "sessions"
    _write(sessions / "main.jsonl", _session_rows("main", "/tmp/app", "Main task"))
    _write(
        sessions / "subagent.jsonl",
        _session_rows("sub", "/tmp/app", "Sub task", source={"subagent": "review"}),
    )
    monkeypatch.setenv("CMAN_CODEX_SESSIONS_DIR", str(sessions))

    results = list_codex_sessions(limit=10)

    assert [item["session_id"] for item in results] == ["main"]
