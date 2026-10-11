"""Check the running API and remote MCP boundary without invoking an LLM."""

from __future__ import annotations

import asyncio
import os
import time

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
MCP_URL = os.getenv("MCP_URL", "http://localhost:8001/mcp")
MAX_ATTEMPTS = 12


async def check_mcp() -> list[str]:
    last_error: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            async with create_mcp_http_client() as http_client:
                async with streamable_http_client(MCP_URL, http_client=http_client) as streams:
                    async with ClientSession(streams[0], streams[1]) as session:
                        await session.initialize()
                        tools = await session.list_tools()
                        return [tool.name for tool in tools.tools]
        except Exception as exc:  # startup races are expected during Compose boot
            last_error = exc
            await asyncio.sleep(min(0.5 * (2**attempt), 3.0))
    raise RuntimeError("MCP smoke check did not become ready") from last_error


def get_json_with_retry(client: httpx.Client, path: str) -> dict:
    last_error: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            response = client.get(f"{API_BASE_URL}{path}")
            if response.status_code < 500:
                response.raise_for_status()
                return response.json()
            response.raise_for_status()
        except (httpx.HTTPError, ValueError) as exc:
            last_error = exc
            time.sleep(min(0.5 * (2**attempt), 3.0))
    raise RuntimeError(f"API smoke check did not become ready: {path}") from last_error


def main() -> None:
    with httpx.Client(timeout=10.0) as client:
        for path in ["/api/health", "/api/ready"]:
            print(path, get_json_with_retry(client, path))

    tool_names = asyncio.run(check_mcp())
    expected = {
        "search_recalls",
        "search_technical_communications",
        "get_service_history",
    }
    missing = expected.difference(tool_names)
    if missing:
        raise SystemExit(f"MCP tools missing: {sorted(missing)}")
    print("MCP tools", sorted(tool_names))
    print("Stack smoke check passed without invoking an LLM.")


if __name__ == "__main__":
    main()
