import json

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from ..schemas import ConcernAnalysis, FinalNarrative
from ..services.llm import get_chat_model
from ..services.risk import deterministic_risk_override
from .state import TriageState
from .tools import TOOLS

AGENT_VERSION = "triage-agent-0.3.0"
PROMPT_VERSION = "triage-prompts-0.2.0"
RETRIEVAL_VERSION = "hybrid-retrieval-0.3.0"


ANALYZE_PROMPT = """You are assisting an automotive service advisor with intake triage.
Extract only what the customer actually reported. Do not diagnose a failed component.
Classify risk as routine, priority, or safety_review. Use safety_review for concerns involving
braking, steering, airbags, fire/smoke/fuel leaks, loss of control, or similarly urgent safety signals.
Create a concise semantic-search query for manufacturer technical communications."""

AGENT_PROMPT = """You are the evidence-gathering agent inside a dealership service-advisor copilot.
Your job is NOT to diagnose or authorize repairs. Use the available tools only when they are relevant:
- search_recalls: use for safety-related, warning-light, defect-like, or serious mechanical concerns.
- search_technical_bulletins: use for mechanical/electrical/driveability/infotainment symptoms where manufacturer guidance may exist.
- get_service_history: use when a vehicle_id is present and prior records may affect triage.
Avoid calling the same tool twice. Do not invent evidence. Once you have enough evidence, stop calling tools and say that the investigation is complete.
"""

FINAL_PROMPT = """You are drafting a service-advisor triage result from collected evidence.
Do not diagnose a specific failed part unless the evidence explicitly states it. Do not tell the customer to perform a repair.
Recommended steps must be inspection/verification steps for a qualified technician.
The work order should summarize CUSTOMER STATES, RELEVANT HISTORY/EVIDENCE, and REQUESTED INSPECTION.
If evidence is weak, conflicting, or the risk is safety_review, require human review. Never fabricate recall or bulletin identifiers.
When evidence is present, mention only source IDs supplied in the evidence. Do not invent citations."""


def analyze_concern(state: TriageState) -> dict:
    request = state["request"]
    llm = get_chat_model().with_structured_output(ConcernAnalysis)
    text = f"""Vehicle: {request['vehicle']['year']} {request['vehicle']['make']} {request['vehicle']['model']}
Mileage: {request['mileage']}
Customer complaint: {request['customer_complaint']}
Advisor notes: {request.get('service_advisor_notes', '')}"""
    analysis = llm.invoke([SystemMessage(content=ANALYZE_PROMPT), HumanMessage(content=text)])
    risk_text = " ".join([
        request["customer_complaint"],
        request.get("service_advisor_notes", ""),
    ])
    analysis.risk_level = deterministic_risk_override(risk_text, analysis.risk_level)
    return {"concern_analysis": analysis.model_dump(), "messages": [HumanMessage(content=text)]}


def agent_step(state: TriageState) -> dict:
    request = state["request"]
    analysis = state["concern_analysis"]
    used = [m.name for m in state.get("messages", []) if isinstance(m, ToolMessage)]
    context = f"""Vehicle: {request['vehicle']}
Concern analysis: {analysis}
Tools already used: {used}
Choose only relevant remaining tools. If enough evidence has already been gathered, finish."""
    llm = get_chat_model().bind_tools(TOOLS)
    response = llm.invoke([SystemMessage(content=AGENT_PROMPT + "\n" + context), *state.get("messages", [])])
    return {"messages": [response]}


def route_after_agent(state: TriageState) -> str:
    last = state["messages"][-1]
    if getattr(last, "tool_calls", None):
        return "tools"
    return "finalize"


def _tool_payloads(messages):
    payloads = {
        "search_recalls": {"status": "not_called", "items": [], "evidence": []},
        "search_technical_bulletins": {"status": "not_called", "items": [], "evidence": []},
        "get_service_history": {"status": "not_called", "items": [], "evidence": []},
    }
    for message in messages:
        if isinstance(message, ToolMessage) and message.name in payloads:
            try:
                parsed = json.loads(message.content)
                # Keep compatibility with the original tool response shape.
                if isinstance(parsed, list):
                    parsed = {"status": "ok", "items": parsed, "evidence": []}
                payloads[message.name] = parsed
            except Exception as exc:
                payloads[message.name] = {
                    "status": "tool_error",
                    "items": [],
                    "evidence": [],
                    "error": str(exc),
                }
    return payloads


def finalize(state: TriageState) -> dict:
    request = state["request"]
    analysis = state["concern_analysis"]
    payloads = _tool_payloads(state.get("messages", []))
    tools_used = [
        name
        for name, values in payloads.items()
        if values["status"] != "not_called"
    ]
    evidence_present = any(values.get("evidence") for values in payloads.values())
    tool_errors = [
        {"tool": name, "error": values.get("error", "unknown tool error")}
        for name, values in payloads.items()
        if values.get("status") == "tool_error"
    ]
    evidence = [
        item
        for values in payloads.values()
        for item in values.get("evidence", [])
    ]

    evidence_for_llm = {
        "risk_level": analysis["risk_level"],
        "parsed_symptoms": analysis["symptoms"],
        "recalls": payloads["search_recalls"].get("items", []),
        "technical_bulletins": payloads["search_technical_bulletins"].get("items", []),
        "service_history": payloads["get_service_history"].get("items", []),
        "evidence": evidence,
        "tool_errors": tool_errors,
        "evidence_present": evidence_present,
    }
    llm = get_chat_model().with_structured_output(FinalNarrative)
    narrative = llm.invoke([
        SystemMessage(content=FINAL_PROMPT),
        HumanMessage(content=json.dumps({"request": request, "evidence": evidence_for_llm}, ensure_ascii=False)),
    ])

    if analysis["risk_level"] == "safety_review" or not evidence_present or tool_errors:
        narrative.human_review_required = True

    result = {
        "risk_level": analysis["risk_level"],
        "parsed_symptoms": analysis["symptoms"],
        "component": analysis["component"],
        "missing_information": analysis["missing_information"],
        "matched_recalls": payloads["search_recalls"].get("items", []),
        "matched_tsb": payloads["search_technical_bulletins"].get("items", []),
        "prior_service_context": payloads["get_service_history"].get("items", []),
        "evidence": evidence,
        "tool_errors": tool_errors,
        "versions": {
            "agent": AGENT_VERSION,
            "prompts": PROMPT_VERSION,
            "retrieval": RETRIEVAL_VERSION,
        },
        "recommended_inspection_steps": narrative.recommended_inspection_steps,
        "human_review_required": narrative.human_review_required,
        "evidence_summary": narrative.evidence_summary,
        "draft_work_order": narrative.draft_work_order,
        "tools_used": tools_used,
    }
    return {"result": result}


def build_graph():
    graph = StateGraph(TriageState)
    graph.add_node("analyze", analyze_concern)
    graph.add_node("agent", agent_step)
    graph.add_node("tools", ToolNode(TOOLS, handle_tool_errors=True))
    graph.add_node("finalize", finalize)

    graph.add_edge(START, "analyze")
    graph.add_edge("analyze", "agent")
    graph.add_conditional_edges("agent", route_after_agent, {"tools": "tools", "finalize": "finalize"})
    graph.add_edge("tools", "agent")
    graph.add_edge("finalize", END)
    return graph.compile()


triage_graph = build_graph()
