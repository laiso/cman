#!/usr/bin/env python3
"""Call cman's MCP server over stdio without external Python packages."""

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def call_search(query: str, source: str, limit: int, server_root: Path) -> str:
    config = json.loads((server_root / ".codex-plugin" / "mcp.json").read_text(encoding="utf-8"))
    launch = config["mcpServers"]["cman"]
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "cman-check", "version": "1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "search_all", "arguments": {"keyword": query, "source": source, "limit": limit}}},
    ]
    result = subprocess.run(
        [launch["command"], *launch["args"]],
        cwd=server_root / launch.get("cwd", "."),
        input="".join(json.dumps(message) + "\n" for message in messages),
        text=True, capture_output=True, check=True,
    )
    responses = {item["id"]: item for item in map(json.loads, result.stdout.splitlines())}
    assert responses[1]["result"]["capabilities"]["tools"] == {"listChanged": False}
    assert "search_all" in {item["name"] for item in responses[2]["result"]["tools"]}
    call = responses[3]["result"]
    if call["isError"]:
        raise RuntimeError(call["content"][0]["text"])
    return call["content"][0]["text"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify cman through MCP stdio")
    parser.add_argument("query")
    parser.add_argument("--source", default="all", choices=("all", "claude", "pi", "codex", "memory"))
    parser.add_argument("-n", "--limit", type=int, default=10)
    parser.add_argument("--server-root", type=Path, default=ROOT)
    args = parser.parse_args()
    output = call_search(args.query, args.source, max(1, args.limit), args.server_root.resolve())
    print(output)
    return 1 if not output or output.startswith("No ") else 0


if __name__ == "__main__":
    sys.exit(main())
