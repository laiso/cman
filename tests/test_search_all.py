"""Tests for scripts/search_all.py."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from search_all import search_all


def _write_jsonl(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_search_all_crosses_claude_pi_and_memory_without_agent_selection(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        home = root / "home"
        claude_dir = home / ".claude"
        claude_project = claude_dir / "projects" / "-home-work-app"
        pi_sessions = home / ".pi" / "agent" / "sessions" / "--home-work-app--"
        codex_sessions = home / ".codex" / "sessions"

        _write_jsonl(claude_project / "claude-session-id.jsonl", [
            {"type": "summary", "cwd": str(home / "work" / "app"), "summary": "cross memory claude summary"},
            {"type": "user", "message": {"content": "Investigate cross memory in Claude"}},
        ])
        _write_jsonl(claude_project / "agent-subagent-id.jsonl", [
            {"type": "user", "message": {"content": "cross memory forbidden-claude-subagent-marker"}},
        ])
        _write_jsonl(pi_sessions / "2026-06-26T00-00-00Z_pi.jsonl", [
            {"type": "session", "id": "pi-session-id", "cwd": str(home / "work" / "app")},
            {"type": "message", "message": {"role": "user", "content": "Investigate cross memory in Pi"}},
        ])
        _write_jsonl(codex_sessions / "codex-session.jsonl", [
            {"type": "session_meta", "payload": {"id": "codex-session-id", "cwd": str(home / "work" / "app"), "source": "cli"}},
            {"type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Investigate cross memory in Codex"}]}},
        ])

        memory_dir = claude_project / "memory"
        memory_dir.mkdir(parents=True)
        (memory_dir / "MEMORY.md").write_text("cross memory note\n", encoding="utf-8")

        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setenv("CMAN_CLAUDE_DIR", str(claude_dir))
        monkeypatch.setenv("CMAN_PI_SESSIONS_DIR", str(home / ".pi" / "agent" / "sessions"))
        monkeypatch.setenv("CMAN_CODEX_SESSIONS_DIR", str(codex_sessions))

        output = search_all("cross memory", limit=10)

        assert "=== Cross-agent memory matching" in output
        assert "Claude ~/work/app" in output
        assert "cd ~/work/app && claude --resume claude-session-id" in output
        assert "Pi ~/work/app" in output
        assert "cd ~/work/app && pi --session pi-session-id" in output
        assert "Codex ~/work/app" in output
        assert "cd ~/work/app && codex resume codex-session-id" in output
        assert "Memory ~/.claude/projects/-home-work-app/memory/MEMORY.md" in output
        assert "forbidden-claude-subagent-marker" not in output
        assert str(home) not in output


def test_search_all_cli_runs_without_agent_flag(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        home = root / "home"
        claude_dir = root / ".claude"
        claude_project = claude_dir / "projects" / "-home-work-app"
        pi_root = root / ".pi" / "agent" / "sessions"
        pi_sessions = pi_root / "--home-work-app--"

        _write_jsonl(claude_project / "claude-session-id.jsonl", [
            {"type": "summary", "cwd": str(home / "work" / "app"), "summary": "cross cli claude"},
        ])
        _write_jsonl(pi_sessions / "2026-06-26T00-00-00Z_pi.jsonl", [
            {"type": "session", "id": "pi-session-id", "cwd": str(home / "work" / "app")},
            {"type": "message", "message": {"role": "user", "content": "cross cli pi"}},
        ])

        env = os.environ.copy()
        env["HOME"] = str(home)
        env["CMAN_CLAUDE_DIR"] = str(claude_dir)
        env["CMAN_PI_SESSIONS_DIR"] = str(pi_root)

        result = subprocess.run(
            [sys.executable, "scripts/search_all.py", "cross cli", "-n", "5", "--no-memory"],
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

        assert "Claude ~/work/app" in result.stdout
        assert "Pi ~/work/app" in result.stdout
        assert str(home) not in result.stdout


def test_search_all_can_be_restricted_to_claude_source(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        home = root / "home"
        claude_dir = home / ".claude"
        claude_project = claude_dir / "projects" / "-home-work-app"
        pi_sessions = home / ".pi" / "agent" / "sessions" / "--home-work-app--"

        _write_jsonl(claude_project / "claude-session-id.jsonl", [
            {"type": "summary", "cwd": str(home / "work" / "app"), "summary": "source filter shared keyword"},
        ])
        _write_jsonl(pi_sessions / "2026-06-26T00-00-00Z_pi.jsonl", [
            {"type": "session", "id": "pi-session-id", "cwd": str(home / "work" / "app")},
            {"type": "message", "message": {"role": "user", "content": "source filter shared keyword"}},
        ])

        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setenv("CMAN_CLAUDE_DIR", str(claude_dir))
        monkeypatch.setenv("CMAN_PI_SESSIONS_DIR", str(home / ".pi" / "agent" / "sessions"))

        output = search_all("source filter", limit=10, source="claude")

        assert "=== Claude memory matching" in output
        assert "Claude ~/work/app" in output
        assert "Pi ~/work/app" not in output
        assert "pi --session" not in output


def test_search_all_can_be_restricted_to_codex_and_excludes_subagents(monkeypatch, tmp_path):
    home = tmp_path / "home"
    sessions = home / ".codex" / "sessions"
    main_rows = [
        {"type": "session_meta", "payload": {"id": "main", "cwd": str(home / "work" / "app"), "source": "cli"}},
        {"type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "cman was updated"}]}},
    ]
    subagent_rows = [
        {"type": "session_meta", "payload": {"id": "sub", "cwd": str(home / "work" / "app"), "source": {"subagent": "review"}}},
        {"type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "cman updates only-subagent-marker"}]}},
    ]
    _write_jsonl(sessions / "main.jsonl", main_rows)
    _write_jsonl(sessions / "sub.jsonl", subagent_rows)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("CMAN_CODEX_SESSIONS_DIR", str(sessions))

    output = search_all("cman updates", source="codex")

    assert "=== Codex memory matching" in output
    assert "codex resume main" in output
    assert "only-subagent-marker" not in output
