from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

RiskLevel = Literal["routine", "priority", "safety_review"]


class VehicleInput(BaseModel):
    year: int = Field(ge=1990, le=2100)
    make: str
    model: str
    vehicle_id: str | None = None


class TriageRequest(BaseModel):
    vehicle: VehicleInput
    mileage: int = Field(ge=0, le=1_000_000)
    customer_complaint: str = Field(min_length=5)
    service_advisor_notes: str = ""


class ConcernAnalysis(BaseModel):
    symptoms: list[str]
    component: str
    risk_level: RiskLevel
    search_query: str
    missing_information: list[str] = Field(default_factory=list)


class FinalNarrative(BaseModel):
    recommended_inspection_steps: list[str]
    human_review_required: bool
    evidence_summary: str
    draft_work_order: str


class EvidenceItem(BaseModel):
    source_type: str
    source_id: str
    source_url: str | None = None
    title: str | None = None
    section: str | None = None
    snippet: str
    confidence: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApprovalRequest(BaseModel):
    work_order: str
    reviewer_id: str = Field(default="local-advisor", min_length=1, max_length=128)


class RejectionRequest(BaseModel):
    reviewer_id: str = Field(default="local-advisor", min_length=1, max_length=128)
    reason: str = Field(min_length=3, max_length=2000)


class TSBSearchRequest(BaseModel):
    year: int
    make: str
    model: str
    query: str
    k: int = Field(default=5, ge=1, le=10)


class TriageRunStatus(BaseModel):
    run_id: str
    status: str
    risk_level: RiskLevel | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
