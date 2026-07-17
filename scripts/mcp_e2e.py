#!/usr/bin/env python3

"""Call cman's MCP server over stdio for local end-to-end verification."""

import argparse
import asyncio
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


ROOT = Path(__file__).resolve().parents[1]


async def call_search(query: str, source: str, limit: int, server_root: Path) -> str:
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(server_root / "server.py")],
        env=os.environ.copy(),
    )
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(
                "search_all",
                arguments={"keyword": query, "source": source, "limit": limit},
            )

    texts = [item.text for item in result.content if hasattr(item, "text")]
    output = "\n".join(texts)
    if result.isError:
        raise RuntimeError(output or "cman MCP search_all failed")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify cman through an external MCP client")
    parser.add_argument("query")
    parser.add_argument("--source", default="all", choices=("all", "claude", "pi", "codex", "memory"))
    parser.add_argument("-n", "--limit", type=int, default=10)
    parser.add_argument("--server-root", type=Path, default=ROOT)
    args = parser.parse_args()

    output = asyncio.run(call_search(args.query, args.source, max(1, args.limit), args.server_root.resolve()))
    print(output)
    if not output or output.startswith("No "):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
