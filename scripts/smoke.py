#!/usr/bin/env python3

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def write_fixture(base_dir: Path) -> tuple[Path, Path, Path]:
    claude_dir = base_dir / ".claude"
    project_dir = claude_dir / "projects" / "-private-tmp-cman-e2e-project"
    project_dir.mkdir(parents=True, exist_ok=True)

    session_id = "11111111-1111-4111-8111-111111111111"
    session = project_dir / f"{session_id}.jsonl"
    rows = [
        {
            "type": "summary",
            "cwd": "/private/tmp/cman-e2e-project",
            "slug": "synthetic-plan",
            "summary": "Synthetic cman smoke summary",
        },
        {"type": "user", "message": {"content": "Investigate cman smoke test"}},
        {
            "type": "assistant",
            "message": {
                "content": "Confirmed the synthetic cman smoke test session is readable."
            },
        },
    ]
    session.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )

    plans_dir = claude_dir / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    (plans_dir / "synthetic-plan.md").write_text(
        "# Synthetic cman E2E plan\n\nThis is safe fixture data.\n",
        encoding="utf-8",
    )

    memory_dir = project_dir / "memory"
    memory_dir.mkdir(exist_ok=True)
    (memory_dir / "MEMORY.md").write_text(
        "- Synthetic memory item for cman E2E\n",
        encoding="utf-8",
    )

    pi_sessions_dir = (
        base_dir
        / ".pi"
        / "agent"
        / "sessions"
        / "--private-tmp-cman-e2e-project--"
    )
    pi_sessions_dir.mkdir(parents=True, exist_ok=True)
    pi_session = pi_sessions_dir / "2026-06-26T00-00-00-000Z_019f01b4-297a.jsonl"
    pi_rows = [
        {
            "type": "session",
            "version": 3,
            "id": "019f01b4-297a",
            "timestamp": "2026-06-26T00:00:00.000Z",
            "cwd": "/private/tmp/cman-e2e-project",
        },
        {
            "type": "message",
            "id": "msg-user",
            "parentId": None,
            "timestamp": "2026-06-26T00:00:01.000Z",
            "message": {
                "role": "user",
                "content": [{"type": "text", "text": "Investigate Pi cman smoke test"}],
            },
        },
        {
            "type": "message",
            "id": "msg-assistant",
            "parentId": "msg-user",
            "timestamp": "2026-06-26T00:00:02.000Z",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "thinking", "text": "internal reasoning not searched"},
                    {
                        "type": "text",
                        "text": "Confirmed the synthetic Pi cman session is readable.",
                    },
                ],
            },
        },
    ]
    pi_session.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in pi_rows) + "\n",
        encoding="utf-8",
    )

    codex_sessions_dir = base_dir / ".codex" / "sessions"
    codex_sessions_dir.mkdir(parents=True, exist_ok=True)
    codex_rows = [
        {
            "type": "session_meta",
            "payload": {
                "id": "codex-smoke-id",
                "cwd": "/private/tmp/cman-e2e-project",
                "source": "cli",
            },
        },
        {
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "Investigate Codex cman updates"}],
            },
        },
        {
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "Confirmed Codex cman smoke memory"}],
            },
        },
    ]
    (codex_sessions_dir / "codex-smoke.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in codex_rows) + "\n",
        encoding="utf-8",
    )
    codex_subagent_rows = [
        {
            "type": "session_meta",
            "payload": {
                "id": "codex-subagent-id",
                "cwd": "/private/tmp/cman-e2e-project",
                "source": {"subagent": "review"},
            },
        },
        {
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "cman forbidden-subagent-marker"}],
            },
        },
    ]
    (codex_sessions_dir / "codex-subagent.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in codex_subagent_rows) + "\n",
        encoding="utf-8",
    )

    return claude_dir, pi_sessions_dir, codex_sessions_dir


def run_command(args, env, cwd=ROOT):
    result = subprocess.run(
        args,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    output = result.stdout + result.stderr
    if result.returncode != 0:
        print(output, file=sys.stderr)
        raise SystemExit(result.returncode)
    return output


def assert_contains(name: str, output: str, expected: str):
    if expected not in output:
        print(f"{name}: expected to find {expected!r}", file=sys.stderr)
        print(output, file=sys.stderr)
        raise SystemExit(1)


def run_script_smoke(claude_dir: Path, pi_sessions_dir: Path, codex_sessions_dir: Path):
    env = os.environ.copy()
    env["CMAN_CLAUDE_DIR"] = str(claude_dir)
    env["CMAN_PI_SESSIONS_DIR"] = str(pi_sessions_dir)
    env["CMAN_CODEX_SESSIONS_DIR"] = str(codex_sessions_dir)

    checks = [
        (
            "sessions",
            ["python3", "scripts/sessions.py", "-n", "5", "--exclude-subagents"],
            "Investigate cman smoke test",
        ),
        (
            "sessions since",
            ["python3", "scripts/sessions.py", "-n", "5", "--exclude-subagents", "--since", "2026-06-26"],
            "Investigate cman smoke test",
        ),
        ("grep", ["python3", "scripts/grep.py", "cman", "-n", "5"], "Confirmed"),
        ("plans", ["python3", "scripts/plans.py"], "Synthetic cman E2E plan"),
        ("memory", ["python3", "scripts/memory.py"], "Synthetic memory item"),
        ("pi sessions", ["python3", "scripts/pi_sessions.py", "-n", "5"], "Investigate Pi cman smoke test"),
        ("pi sessions since", ["python3", "scripts/pi_sessions.py", "-n", "5", "--since", "2026-06-26"], "Investigate Pi cman smoke test"),
        ("pi grep", ["python3", "scripts/pi_sessions.py", "Pi cman", "-n", "5"], "Confirmed"),
        ("codex sessions", ["python3", "scripts/codex_sessions.py", "-n", "5"], "Investigate Codex cman updates"),
        ("codex grep", ["python3", "scripts/codex_sessions.py", "cman updates", "-n", "5"], "codex resume codex-smoke-id"),
        ("cross search", ["python3", "scripts/search_all.py", "cman", "-n", "10"], "Cross-agent memory matching"),
        ("server", ["python3", "server.py", "--smoke"], "ok mcp sessions"),
    ]

    for name, command, expected in checks:
        output = run_command(command, env)
        assert_contains(name, output, expected)
        print(f"ok {name}")


def run_missing_plans_regression(claude_dir: Path, pi_sessions_dir: Path, codex_sessions_dir: Path):
    plans_dir = claude_dir / "plans"
    if plans_dir.exists():
        shutil.rmtree(plans_dir)

    env = os.environ.copy()
    env["CMAN_CLAUDE_DIR"] = str(claude_dir)
    env["CMAN_PI_SESSIONS_DIR"] = str(pi_sessions_dir)
    env["CMAN_CODEX_SESSIONS_DIR"] = str(codex_sessions_dir)
    output = run_command(["python3", "scripts/plans.py"], env)
    assert_contains("missing plans script", output, "No sessions found")

    output = run_command(["python3", "server.py", "--smoke"], env)
    assert_contains("missing plans server", output, "ok mcp plans")
    print("ok missing plans regression")


def run_skill_mcp_smoke():
    skill_files = [
        ROOT / "skills" / "remember" / "SKILL.md",
        ROOT / "skills" / "cm-status" / "SKILL.md",
    ]
    for skill_file in skill_files:
        if not skill_file.exists():
            print(f"skill mcp: missing {skill_file}", file=sys.stderr)
            raise SystemExit(1)
        text = skill_file.read_text(encoding="utf-8")
        assert_contains(str(skill_file), text, "mcp__plugin_cman_cman__*")
        assert_contains(str(skill_file), text, "mcp__cman__*")

    remember_text = (ROOT / "skills" / "remember" / "SKILL.md").read_text(encoding="utf-8")
    for tool_name in (
        "list_sessions",
        "list_plans",
        "list_memory",
        "search_sessions",
        "list_pi_sessions",
        "search_pi_sessions",
        "list_codex_sessions",
        "search_codex_sessions",
        "search_all",
    ):
        assert_contains("remember tools", remember_text, tool_name)

    status_text = (ROOT / "skills" / "cm-status" / "SKILL.md").read_text(encoding="utf-8")
    for tool_name in ("list_sessions", "list_plans", "list_memory", "list_pi_sessions", "list_codex_sessions"):
        assert_contains("cm-status tools", status_text, tool_name)

    print("ok skill mcp declarations")


def run_plugin_validation():
    if not shutil.which("claude"):
        print("skip plugin validation: claude command not found")
        return
    output = run_command(["claude", "plugin", "validate", str(ROOT)], os.environ.copy())
    assert_contains("plugin validate", output, "Validation passed")
    print("ok plugin validate")


def claude_logged_in() -> bool:
    if not shutil.which("claude"):
        return False
    result = subprocess.run(
        ["claude", "auth", "status"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        return False
    try:
        status = json.loads(result.stdout)
    except json.JSONDecodeError:
        return False
    return bool(status.get("loggedIn"))


def run_claude_e2e(claude_dir: Path, pi_sessions_dir: Path, codex_sessions_dir: Path):
    if not shutil.which("claude"):
        print("claude command not found", file=sys.stderr)
        raise SystemExit(1)

    if not claude_logged_in():
        print("skip claude e2e: claude is not logged in")
        return

    workdir = Path("/private/tmp/cman-e2e-project")
    workdir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["CMAN_CLAUDE_DIR"] = str(claude_dir)
    env["CMAN_PI_SESSIONS_DIR"] = str(pi_sessions_dir)
    env["CMAN_CODEX_SESSIONS_DIR"] = str(codex_sessions_dir)
    base_command = [
        "claude",
        "--plugin-dir",
        str(ROOT),
        "--no-session-persistence",
        "--max-budget-usd",
        "0.25",
        "--allowedTools",
        "mcp__plugin_cman_cman__*,Read",
        "-p",
    ]

    status_prompt = (
        "Use the cman MCP tools directly. Call list_sessions with limit=5, "
        "then call list_pi_sessions with limit=5. Summarize the raw results."
    )
    status_output = run_command(base_command + [status_prompt], env, cwd=workdir)
    assert_contains("claude e2e status", status_output, "cman-e2e-project")
    assert_contains("claude e2e status", status_output, "Pi")

    search_prompt = (
        "Use the cman MCP tools directly. Call search_sessions for keyword cman, "
        "then call search_pi_sessions for keyword cman. Summarize the raw results."
    )
    remember_output = run_command(base_command + [search_prompt], env, cwd=workdir)
    assert_contains("claude e2e search", remember_output, "cman")

    print("ok claude e2e")


def run_pi_e2e():
    if not shutil.which("pi"):
        print("pi command not found", file=sys.stderr)
        raise SystemExit(1)

    with tempfile.TemporaryDirectory(prefix="cman-pi-e2e-") as tmp:
        root = Path(tmp)
        claude_dir = root / ".claude"
        claude_project = claude_dir / "projects" / "-tmp-work-app"
        pi_sessions_dir = root / ".pi" / "agent" / "sessions"
        pi_project = pi_sessions_dir / "--tmp-work-app--"
        claude_project.mkdir(parents=True, exist_ok=True)
        pi_project.mkdir(parents=True, exist_ok=True)

        (claude_project / "claude-e2e-id.jsonl").write_text(
            "\n".join([
                json.dumps({
                    "type": "summary",
                    "cwd": "/tmp/work/app",
                    "summary": "cross e2e claude summary",
                }),
                json.dumps({
                    "type": "user",
                    "message": {"content": "cross e2e claude work"},
                }),
            ]) + "\n",
            encoding="utf-8",
        )
        (pi_project / "2026-06-26T00-00-00Z_pi.jsonl").write_text(
            "\n".join([
                json.dumps({
                    "type": "session",
                    "version": 3,
                    "id": "pi-e2e-id",
                    "timestamp": "2026-06-26T00:00:00.000Z",
                    "cwd": "/tmp/work/app",
                }),
                json.dumps({
                    "type": "message",
                    "message": {"role": "user", "content": "cross e2e pi work"},
                }),
            ]) + "\n",
            encoding="utf-8",
        )
        memory_dir = claude_project / "memory"
        memory_dir.mkdir(exist_ok=True)
        (memory_dir / "MEMORY.md").write_text("cross e2e memory note\n", encoding="utf-8")

        env = os.environ.copy()
        env["CMAN_CLAUDE_DIR"] = str(claude_dir)
        env["CMAN_PI_SESSIONS_DIR"] = str(pi_sessions_dir)
        env["PI_OFFLINE"] = "1"
        command = [
            "pi",
            "--no-extensions",
            "-e",
            str(ROOT / "pi" / "extensions" / "index.js"),
            "--verbose",
            "--no-session",
            "--tools",
            "cman_search_all,cman_claude_sessions",
            "-p",
            "Use cman_claude_sessions with limit 5, then use cman_search_all with query cross e2e and limit 10. Output only the raw tool results.",
        ]
        result = subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        output = result.stdout + result.stderr
        if result.returncode != 0 and "No API key found" in output:
            print("skip pi e2e: pi provider is not logged in")
            return
        if result.returncode != 0:
            print(output, file=sys.stderr)
            raise SystemExit(result.returncode)
        assert_contains("pi e2e cross", output, "Cross-agent memory matching")
        assert_contains("pi e2e claude", output, "claude --resume claude-e2e-id")
        assert_contains("pi e2e pi", output, "pi --session pi-e2e-id")
        assert_contains("pi e2e memory", output, "cross e2e memory note")
        print("ok pi e2e")


def main():
    parser = argparse.ArgumentParser(description="Run cman smoke tests with fixture data")
    parser.add_argument(
        "--claude-e2e",
        action="store_true",
        help="Also invoke Claude Code with the local plugin; requires Claude login",
    )
    parser.add_argument(
        "--pi-e2e",
        action="store_true",
        help="Also invoke Pi with the local extension; requires Pi provider login",
    )
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="cman-smoke-") as tmp:
        claude_dir, pi_sessions_dir, codex_sessions_dir = write_fixture(Path(tmp))
        run_script_smoke(claude_dir, pi_sessions_dir, codex_sessions_dir)
        run_skill_mcp_smoke()
        run_missing_plans_regression(claude_dir, pi_sessions_dir, codex_sessions_dir)
        run_plugin_validation()

        if args.claude_e2e:
            run_claude_e2e(claude_dir, pi_sessions_dir, codex_sessions_dir)
        if args.pi_e2e:
            run_pi_e2e()

    return 0


if __name__ == "__main__":
    sys.exit(main())
