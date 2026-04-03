"""Tests for scripts/grep.py — session search and memory search."""

import json
import os
import tempfile
from pathlib import Path

import sys

# Allow importing from scripts/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from grep import (
    _tokenize_query,
    _all_tokens_match,
    _extract_snippet,
    search_session,
    search_memory_files,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_session(tmp_dir, session_id, lines):
    """Write a JSONL session file and return its Path."""
    p = tmp_dir / f"{session_id}.jsonl"
    with open(p, "w", encoding="utf-8") as f:
        for obj in lines:
            f.write(json.dumps(obj) + "\n")
    return p


# ---------------------------------------------------------------------------
# _tokenize_query
# ---------------------------------------------------------------------------

def test_tokenize_single_word():
    assert _tokenize_query("DynamoDB") == ["dynamodb"]


def test_tokenize_multi_word():
    assert _tokenize_query("DynamoDB billing") == ["dynamodb", "billing"]


def test_tokenize_extra_whitespace():
    assert _tokenize_query("  foo   bar  ") == ["foo", "bar"]


def test_tokenize_empty():
    assert _tokenize_query("") == []
    assert _tokenize_query("   ") == []


# ---------------------------------------------------------------------------
# _all_tokens_match
# ---------------------------------------------------------------------------

def test_all_tokens_match_single():
    assert _all_tokens_match(["hello"], "hello world")


def test_all_tokens_match_multi():
    assert _all_tokens_match(["hello", "world"], "hello beautiful world")


def test_all_tokens_no_match():
    assert not _all_tokens_match(["hello", "missing"], "hello world")


def test_all_tokens_order_independent():
    assert _all_tokens_match(["world", "hello"], "hello world")


# ---------------------------------------------------------------------------
# _extract_snippet
# ---------------------------------------------------------------------------

def test_snippet_short_content():
    assert _extract_snippet("short text", ["short"]) == "short text"


def test_snippet_long_content_centres_on_token():
    content = "a" * 100 + " TARGET " + "b" * 100
    snippet = _extract_snippet(content, ["target"])
    assert "TARGET" in snippet
    assert snippet.startswith("...")


def test_snippet_no_match_returns_start():
    content = "x" * 300
    snippet = _extract_snippet(content, ["zzz"])
    # Should return the beginning of the content
    assert snippet.startswith("x")


# ---------------------------------------------------------------------------
# search_session  — single-token (backwards compat)
# ---------------------------------------------------------------------------

def test_search_session_single_keyword():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        p = _write_session(tmp, "sess1", [
            {"cwd": "/home/user/project"},
            {"type": "user", "message": {"content": "Fix the DynamoDB table"}},
            {"type": "assistant", "message": {"content": "Done fixing DynamoDB."}},
        ])
        result = search_session(p, "DynamoDB", 3)
        assert result is not None
        assert result["session_id"] == "sess1"
        assert result["cwd"] == "/home/user/project"
        assert len(result["matches"]) == 2
        assert result["score"] > 0


def test_search_session_no_match():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        p = _write_session(tmp, "sess2", [
            {"type": "user", "message": {"content": "Hello world"}},
        ])
        result = search_session(p, "nonexistent", 3)
        assert result is None


# ---------------------------------------------------------------------------
# search_session  — multi-token AND
# ---------------------------------------------------------------------------

def test_search_session_multi_token_match():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        p = _write_session(tmp, "sess3", [
            {"type": "user", "message": {"content": "Check the DynamoDB billing costs"}},
        ])
        result = search_session(p, "DynamoDB billing", 3)
        assert result is not None
        assert result["session_id"] == "sess3"


def test_search_session_multi_token_partial_no_match():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        p = _write_session(tmp, "sess4", [
            {"type": "user", "message": {"content": "Check the DynamoDB table"}},
        ])
        # "billing" is missing
        result = search_session(p, "DynamoDB billing", 3)
        assert result is None


def test_search_session_multi_token_order_independent():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        p = _write_session(tmp, "sess5", [
            {"type": "user", "message": {"content": "billing for DynamoDB"}},
        ])
        result = search_session(p, "DynamoDB billing", 3)
        assert result is not None


# ---------------------------------------------------------------------------
# Relevance scoring
# ---------------------------------------------------------------------------

def test_user_messages_score_higher():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        # Session A: only assistant matches
        pa = _write_session(tmp, "sessA", [
            {"type": "assistant", "message": {"content": "DynamoDB info"}},
        ])
        # Session B: user match
        pb = _write_session(tmp, "sessB", [
            {"type": "user", "message": {"content": "DynamoDB info"}},
        ])
        ra = search_session(pa, "DynamoDB", 3)
        rb = search_session(pb, "DynamoDB", 3)
        assert ra is not None and rb is not None
        assert rb["score"] > ra["score"]


def test_more_matches_yield_higher_score():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        pa = _write_session(tmp, "sessA", [
            {"type": "user", "message": {"content": "DynamoDB"}},
        ])
        pb = _write_session(tmp, "sessB", [
            {"type": "user", "message": {"content": "DynamoDB one"}},
            {"type": "user", "message": {"content": "DynamoDB two"}},
            {"type": "user", "message": {"content": "DynamoDB three"}},
        ])
        ra = search_session(pa, "DynamoDB", 5)
        rb = search_session(pb, "DynamoDB", 5)
        assert rb["score"] > ra["score"]


# ---------------------------------------------------------------------------
# max_matches respected (keeps counting score beyond max_matches)
# ---------------------------------------------------------------------------

def test_max_matches_limits_snippets_but_counts_score():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        p = _write_session(tmp, "sessM", [
            {"type": "user", "message": {"content": "DynamoDB one"}},
            {"type": "user", "message": {"content": "DynamoDB two"}},
            {"type": "user", "message": {"content": "DynamoDB three"}},
        ])
        result = search_session(p, "DynamoDB", max_matches=1)
        assert result is not None
        assert len(result["matches"]) == 1  # only 1 snippet
        assert result["score"] == 9.0  # 3 user matches × weight 3


# ---------------------------------------------------------------------------
# Subagent filtering
# ---------------------------------------------------------------------------

def test_search_session_subagent_file():
    """search_session itself doesn't filter — filtering is at caller level."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        p = _write_session(tmp, "agent-abc123", [
            {"type": "user", "message": {"content": "DynamoDB"}},
        ])
        # The function returns results regardless; filtering is caller's job
        result = search_session(p, "DynamoDB", 3)
        assert result is not None
        assert result["session_id"] == "agent-abc123"


# ---------------------------------------------------------------------------
# Summary messages are indexed
# ---------------------------------------------------------------------------

def test_search_session_indexes_summary():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        p = _write_session(tmp, "sessSum", [
            {"type": "summary", "message": {"content": "Fixed DynamoDB billing issue"}},
        ])
        result = search_session(p, "DynamoDB", 3)
        assert result is not None
        assert result["matches"][0][0] == "summary"


# ---------------------------------------------------------------------------
# search_memory_files
# ---------------------------------------------------------------------------

def test_search_memory_files_match():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        md = tmp / "MEMORY.md"
        md.write_text("# Auth notes\nUse JWT tokens for authentication.\n")
        mem_files = [("auto-memory", md)]
        results = search_memory_files("JWT authentication", mem_files)
        assert len(results) == 1
        assert results[0]["scope"] == "auto-memory"
        assert "JWT" in results[0]["snippet"]


def test_search_memory_files_no_match():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        md = tmp / "MEMORY.md"
        md.write_text("# Random notes\nNothing relevant here.\n")
        mem_files = [("auto-memory", md)]
        results = search_memory_files("DynamoDB", mem_files)
        assert len(results) == 0


def test_search_memory_files_none():
    assert search_memory_files("test", None) == []
    assert search_memory_files("", [("scope", Path("/fake"))]) == []


# ---------------------------------------------------------------------------
# Content as list (array of content blocks)
# ---------------------------------------------------------------------------

def test_search_session_content_array():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        p = _write_session(tmp, "sessList", [
            {"type": "user", "message": {"content": [
                {"type": "text", "text": "Check DynamoDB"},
                {"type": "text", "text": "billing report"},
            ]}},
        ])
        result = search_session(p, "DynamoDB billing", 3)
        assert result is not None


# ---------------------------------------------------------------------------
# Empty / whitespace keyword
# ---------------------------------------------------------------------------

def test_search_session_empty_keyword():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        p = _write_session(tmp, "sessEmpty", [
            {"type": "user", "message": {"content": "anything"}},
        ])
        result = search_session(p, "", 3)
        assert result is None
        result2 = search_session(p, "   ", 3)
        assert result2 is None
