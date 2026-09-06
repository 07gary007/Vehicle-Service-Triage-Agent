from typing import Annotated, Any, TypedDict
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class TriageState(TypedDict, total=False):
    request: dict[str, Any]
    concern_analysis: dict[str, Any]
    messages: Annotated[list[AnyMessage], add_messages]
    result: dict[str, Any]
