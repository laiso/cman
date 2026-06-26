"""Regression tests for scripts/plans.py."""

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_missing_plans_dir_is_not_fatal(tmp_path):
    claude_dir = tmp_path / ".claude"
    project_dir = claude_dir / "projects" / "-tmp-project"
    project_dir.mkdir(parents=True)
    session = project_dir / "session-1.jsonl"
    session.write_text(
        json.dumps(
            {
                "type": "summary",
                "cwd": str(tmp_path / "project"),
                "slug": "missing-plan",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["CMAN_CLAUDE_DIR"] = str(claude_dir)

    result = subprocess.run(
        [sys.executable, "scripts/plans.py"],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0
    assert "=== Claude Code Plans ===" in result.stdout
    assert "No sessions found" in result.stdout
    assert "not found" not in result.stderr
