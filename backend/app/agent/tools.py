
from langchain_core.tools import tool

from ..config import get_settings
from ..domain.tool_service import (
    as_tool_json,
    lookup_recalls,
    lookup_service_history,
    search_technical_communications,
)
from ..mcp_client import call_remote_tool


@tool
def search_recalls(year: int, make: str, model: str, symptoms: str) -> str:
    """Search official NHTSA recalls for a vehicle, ranked against the current symptoms."""
    if get_settings().agent_tool_mode.lower() == "mcp":
        return as_tool_json(call_remote_tool("search_recalls", {
            "year": year,
            "make": make,
            "model": model,
            "symptoms": symptoms,
        }))
    return as_tool_json(lookup_recalls(year, make, model, symptoms))


@tool
def search_technical_bulletins(year: int, make: str, model: str, query: str, k: int = 5) -> str:
    """Semantic search over ingested NHTSA manufacturer technical-communication records for this vehicle."""
    if get_settings().agent_tool_mode.lower() == "mcp":
        return as_tool_json(call_remote_tool("search_technical_communications", {
            "year": year,
            "make": make,
            "model": model,
            "query": query,
            "k": k,
        }))
    return as_tool_json(search_technical_communications(year, make, model, query, k=k))


@tool
def get_service_history(vehicle_id: str, limit: int = 8) -> str:
    """Read prior dealership service records and technician notes for this specific demo vehicle."""
    if get_settings().agent_tool_mode.lower() == "mcp":
        return as_tool_json(call_remote_tool("get_service_history", {
            "vehicle_id": vehicle_id,
            "limit": limit,
        }))
    return as_tool_json(lookup_service_history(vehicle_id, limit=limit))


TOOLS = [search_recalls, search_technical_bulletins, get_service_history]
