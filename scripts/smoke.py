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


def write_fixture(base_dir: Path) -> Path:
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

    return claude_dir


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


def run_script_smoke(claude_dir: Path):
    env = os.environ.copy()
    env["CMAN_CLAUDE_DIR"] = str(claude_dir)

    checks = [
        (
            "sessions",
            ["python3", "scripts/sessions.py", "-n", "5", "--exclude-subagents"],
            "Investigate cman smoke test",
        ),
        ("grep", ["python3", "scripts/grep.py", "cman", "-n", "5"], "Confirmed"),
        ("plans", ["python3", "scripts/plans.py"], "Synthetic cman E2E plan"),
        ("memory", ["python3", "scripts/memory.py"], "Synthetic memory item"),
        ("server", ["python3", "server.py", "--smoke"], "ok mcp sessions"),
    ]

    for name, command, expected in checks:
        output = run_command(command, env)
        assert_contains(name, output, expected)
        print(f"ok {name}")


def run_missing_plans_regression(claude_dir: Path):
    plans_dir = claude_dir / "plans"
    if plans_dir.exists():
        shutil.rmtree(plans_dir)

    env = os.environ.copy()
    env["CMAN_CLAUDE_DIR"] = str(claude_dir)
    output = run_command(["python3", "scripts/plans.py"], env)
    assert_contains("missing plans script", output, "No sessions found")

    output = run_command(["python3", "server.py", "--smoke"], env)
    assert_contains("missing plans server", output, "ok mcp plans")
    print("ok missing plans regression")


def run_skill_mcp_smoke():
    skill_files = [
        ROOT / "skills" / "remember" / "SKILL.md",
        ROOT / "skills" / "cm-search" / "SKILL.md",
        ROOT / "skills" / "cm-status" / "SKILL.md",
    ]
    for skill_file in skill_files:
        if not skill_file.exists():
            print(f"skill mcp: missing {skill_file}", file=sys.stderr)
            raise SystemExit(1)
        text = skill_file.read_text(encoding="utf-8")
        assert_contains(str(skill_file), text, "allowed-tools: mcp__plugin_cman_cman__*")

    search_text = (ROOT / "skills" / "cm-search" / "SKILL.md").read_text(encoding="utf-8")
    for tool_name in ("list_sessions", "list_plans", "list_memory", "search_sessions"):
        assert_contains("cm-search tools", search_text, tool_name)

    status_text = (ROOT / "skills" / "cm-status" / "SKILL.md").read_text(encoding="utf-8")
    for tool_name in ("list_sessions", "list_plans", "list_memory"):
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


def run_claude_e2e(claude_dir: Path):
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

    status_output = run_command(base_command + ["/cman:cm-status all"], env, cwd=workdir)
    assert_contains("claude e2e status", status_output, "Investigate cman smoke test")

    remember_output = run_command(base_command + ["/remember cman"], env, cwd=workdir)
    assert_contains("claude e2e remember", remember_output, "cman")

    print("ok claude e2e")


def main():
    parser = argparse.ArgumentParser(description="Run cman smoke tests with fixture data")
    parser.add_argument(
        "--claude-e2e",
        action="store_true",
        help="Also invoke Claude Code with the local plugin; requires Claude login",
    )
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="cman-smoke-") as tmp:
        claude_dir = write_fixture(Path(tmp))
        run_script_smoke(claude_dir)
        run_skill_mcp_smoke()
        run_missing_plans_regression(claude_dir)
        run_plugin_validation()

        if args.claude_e2e:
            run_claude_e2e(claude_dir)

    return 0


if __name__ == "__main__":
    sys.exit(main())
