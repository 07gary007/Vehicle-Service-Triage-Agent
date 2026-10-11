"""MCP server entry point.

The server can run over stdio for local inspection or Streamable HTTP for a
remote agent client. It intentionally exposes read-only evidence tools; the
approval/write boundary remains in the application API.
"""

from __future__ import annotations

import argparse
from typing import Any

import uvicorn
from mcp.server.mcpserver import MCPServer
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from ..config import get_settings
from ..domain.tool_service import (
    lookup_recalls,
    lookup_service_history,
    search_technical_communications,
)

server = MCPServer(
    name="vehicle-service-tools",
    version="0.3.0",
    instructions=(
        "Read-only evidence tools for vehicle service triage. "
        "Do not use these tools to authorize repairs or diagnose a failed part."
    ),
)


@server.tool(
    name="search_recalls",
    description="Search official NHTSA recalls for a vehicle and rank them against reported symptoms.",
    structured_output=True,
)
def search_recalls(year: int, make: str, model: str, symptoms: str) -> dict[str, Any]:
    return lookup_recalls(year, make, model, symptoms)


@server.tool(
    name="search_technical_communications",
    description="Hybrid-search manufacturer technical communications for a vehicle concern.",
    structured_output=True,
)
def search_technical_communications_tool(
    year: int,
    make: str,
    model: str,
    query: str,
    k: int = 5,
) -> dict[str, Any]:
    return search_technical_communications(year, make, model, query, k=k)


@server.tool(
    name="get_service_history",
    description="Read prior dealership service records for a vehicle ID.",
    structured_output=True,
)
def get_service_history(vehicle_id: str, limit: int = 8) -> dict[str, Any]:
    return lookup_service_history(vehicle_id, limit=limit)


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Small deployment guard for the demo MCP endpoint.

    In Azure, this should be replaced or complemented by Entra authentication
    at the gateway. Keeping the check here makes accidental public exposure
    less likely when the container is run directly.
    """

    async def dispatch(self, request: Request, call_next):
        expected = get_settings().mcp_api_key
        if expected and request.url.path.startswith("/mcp"):
            supplied = request.headers.get("x-mcp-api-key", "")
            if supplied != expected:
                return JSONResponse({"detail": "Unauthorized"}, status_code=401)
        return await call_next(request)


def build_http_app():
    app = server.streamable_http_app(
        streamable_http_path="/mcp",
        json_response=True,
        stateless_http=True,
        host="0.0.0.0",
    )

    def health(_request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "service": "mcp"})

    app.add_route("/health", health, methods=["GET"])
    app.add_middleware(APIKeyMiddleware)
    return app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()

    if args.transport == "stdio":
        server.run("stdio")
        return

    uvicorn.run(build_http_app(), host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
