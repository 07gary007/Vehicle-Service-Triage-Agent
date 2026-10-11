"""Minimal MCP client bridge used by the LangGraph tool adapter.

The default local mode keeps development and unit tests self-contained. Setting
AGENT_TOOL_MODE=mcp makes the agent call the remote Streamable HTTP MCP server,
which is the mode used by the full Docker Compose stack.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

from .config import get_settings


async def _call_remote_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    headers = {"x-mcp-api-key": settings.mcp_api_key} if settings.mcp_api_key else None
    async with create_mcp_http_client(headers=headers) as http_client:
        async with streamable_http_client(
            settings.mcp_server_url,
            http_client=http_client,
        ) as streams:
            read_stream, write_stream = streams[:2]
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(name, arguments=arguments)

    structured = getattr(result, "structured_content", None)
    if structured:
        return structured

    for item in getattr(result, "content", []):
        if getattr(item, "type", None) == "text":
            try:
                return json.loads(item.text)
            except (TypeError, json.JSONDecodeError):
                return {"status": "error", "error": item.text}
    return {"status": "error", "error": "MCP tool returned no content"}


def call_remote_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_call_remote_tool(name, arguments))

    # LangGraph currently invokes these synchronous adapters from a worker
    # thread. If an async caller uses this bridge directly, use a short-lived
    # thread instead of nesting asyncio.run inside an active event loop.
    import threading

    result: dict[str, Any] = {}
    error: list[BaseException] = []

    def runner() -> None:
        try:
            result.update(asyncio.run(_call_remote_tool(name, arguments)))
        except BaseException as exc:  # pragma: no cover - defensive async bridge
            error.append(exc)

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join(timeout=get_settings().nhtsa_timeout_seconds + 20)
    if error:
        raise RuntimeError(f"MCP tool {name} failed") from error[0]
    if not result:
        raise TimeoutError(f"MCP tool {name} timed out")
    return result
