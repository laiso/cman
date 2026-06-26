#!/usr/bin/env python3

"""Guardrails for user-supplied recursive scan roots."""

from __future__ import annotations

import os
from pathlib import Path


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def ensure_allowed_path(path: str | Path | None, roots: list[str | Path], label: str = "path") -> Path | None:
    if path is None:
        return None
    target = Path(path).expanduser()
    if os.environ.get("CMAN_ALLOW_ARBITRARY_PATH") == "1":
        return target
    allowed = [Path(root).expanduser() for root in roots]
    if not any(_is_relative_to(target, root) for root in allowed):
        joined = " or ".join(str(root) for root in allowed)
        raise ValueError(f"{label} must be inside {joined}. Set CMAN_ALLOW_ARBITRARY_PATH=1 to override.")
    return target
