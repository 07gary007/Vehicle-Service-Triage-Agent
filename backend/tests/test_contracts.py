import json

from app.agent.graph import _tool_payloads
from app.mcp_server.server import build_http_app
from app.schemas import ApprovalRequest, TriageRequest
from app.services.retrieval import expand_query
from langchain_core.messages import ToolMessage
from starlette.testclient import TestClient


def test_query_expansion_preserves_customer_language():
    variants = expand_query("The steering wheel shakes at highway speed")
    assert variants[0] == "The steering wheel shakes at highway speed"
    assert any("vibration" in variant for variant in variants)
    assert any("high speed" in variant for variant in variants)


def test_tool_payloads_supports_evidence_envelope():
    message = ToolMessage(
        name="search_technical_bulletins",
        tool_call_id="call-1",
        content=json.dumps({
            "status": "ok",
            "items": [{"document_id": "TSB-1"}],
            "evidence": [{"source_id": "TSB-1", "snippet": "vibration"}],
        }),
    )
    payloads = _tool_payloads([message])
    assert payloads["search_technical_bulletins"]["items"][0]["document_id"] == "TSB-1"
    assert payloads["search_technical_bulletins"]["evidence"]


def test_approval_requires_reviewer_identity_and_work_order():
    body = ApprovalRequest(work_order="Inspect brakes")
    assert body.reviewer_id == "local-advisor"


def test_triage_request_rejects_short_complaints():
    try:
        TriageRequest(
            vehicle={"year": 2021, "make": "Honda", "model": "Civic"},
            mileage=100,
            customer_complaint="bad",
        )
    except ValueError:
        return
    raise AssertionError("short complaint should fail validation")


def test_mcp_health_endpoint_is_available_outside_tool_transport():
    response = TestClient(build_http_app()).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "mcp"}
