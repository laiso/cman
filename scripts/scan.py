#!/usr/bin/env python3

"""Bounded recursive file iteration."""

from __future__ import annotations

import os
from pathlib import Path


def max_scan_files() -> int:
    try:
        return max(1, int(os.environ.get("CMAN_MAX_SCAN_FILES", "20000")))
    except ValueError:
        return 20000


def iter_jsonl_files(root: Path):
    limit = max_scan_files()
    for index, path in enumerate(root.rglob("*.jsonl")):
        if index >= limit:
            break
        yield path
