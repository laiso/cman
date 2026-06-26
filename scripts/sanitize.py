#!/usr/bin/env python3

"""Output hardening helpers for cman CLIs/MCP tools."""

from __future__ import annotations

import os
import re
import shlex
from pathlib import Path

# ANSI CSI plus OSC/DCS/PM/APC escape sequences. Keep this conservative and
# strip before returning text to terminals or agent UIs.
_ANSI_RE = re.compile(
    r"\x1b(?:"
    r"\[[0-?]*[ -/]*[@-~]|"
    r"\][^\x07\x1b]*(?:\x07|\x1b\\)|"
    r"[P^_][^\x1b]*(?:\x1b\\)|"
    r"[@-_]"
    r")"
)
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def strip_unsafe_terminal(text: object) -> str:
    """Remove terminal control sequences/chars while preserving tabs/newlines."""
    value = str(text) if text is not None else ""
    value = _ANSI_RE.sub("", value)
    return _CONTROL_RE.sub("�", value)


def fold_home(text: object, home: str | None = None) -> str:
    value = strip_unsafe_terminal(text)
    h = home or os.environ.get("HOME", str(Path.home()))
    return value.replace(h, "~") if h else value


def display_path(value: str | Path | None, home: str | None = None) -> str:
    if not value:
        return "unknown"
    text = strip_unsafe_terminal(value)
    h = home or os.environ.get("HOME", str(Path.home()))
    return text.replace(h, "~", 1) if h and text.startswith(h) else text


def _shell_path_token(path: str | Path) -> str:
    text = strip_unsafe_terminal(path)
    home = os.environ.get("HOME", str(Path.home()))
    if home and (text == home or text.startswith(home + os.sep)):
        rel = text[len(home):].lstrip(os.sep)
        return "~" if not rel else f"~/{shlex.quote(rel)}"
    return shlex.quote(text)


def shell_cd_command(cwd: str | Path, executable: str, flag: str, identifier: str) -> str:
    """Return a copy-paste-safe resume command without leaking $HOME."""
    return (
        f"cd {_shell_path_token(cwd)} && "
        f"{shlex.quote(executable)} {shlex.quote(flag)} {shlex.quote(strip_unsafe_terminal(identifier))}"
    )


def resume_command(executable: str, flag: str, identifier: str) -> str:
    return f"{shlex.quote(executable)} {shlex.quote(flag)} {shlex.quote(strip_unsafe_terminal(identifier))}"
