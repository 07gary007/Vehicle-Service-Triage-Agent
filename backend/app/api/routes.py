from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..agent.graph import AGENT_VERSION, RETRIEVAL_VERSION, triage_graph
from ..config import get_settings
from ..db import SessionLocal, check_database
from ..models import TriageEvent, TriageRun
from ..schemas import (
    ApprovalRequest,
    RejectionRequest,
    TriageRequest,
    TriageRunStatus,
    TSBSearchRequest,
)
from ..services.llm import model_identifier, validate_model_config
from ..services.retrieval import search_tsb_chunks

router = APIRouter(prefix="/api")


def _record_event(
    db,
    run: TriageRun,
    event_type: str,
    payload: dict[str, Any] | None = None,
    node_name: str | None = None,
) -> None:
    db.add(TriageEvent(
        run_id=run.id,
        event_type=event_type,
        node_name=node_name,
        payload=payload or {},
    ))


def _status_payload(run: TriageRun) -> dict[str, Any]:
    return {
        "run_id": run.public_id,
        "status": run.status,
        "risk_level": run.risk_level,
        "result": run.result_payload,
        "error": run.error_message,
        "created_at": run.created_at,
        "updated_at": run.updated_at,
    }


def _run_graph(request: TriageRequest, run_id: int | None = None) -> dict[str, Any]:
    settings = get_settings()
    output = triage_graph.invoke(
        {"request": request.model_dump(), "messages": []},
        config={
            "recursion_limit": settings.max_triage_recursion,
            "configurable": {"thread_id": str(run_id or "local")},
        },
    )
    return output["result"]


@router.get("/health")
def health():
    return {"status": "ok", "version": get_settings().app_version}


@router.get("/ready")
def ready():
    try:
        check_database()
        validate_model_config()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="dependencies_not_ready") from exc
    return {"status": "ready"}


@router.post("/triage")
def triage(
    request: TriageRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    """Synchronous compatibility endpoint for local demos and evals."""
    run_id: int
    with SessionLocal() as db:
        if idempotency_key:
            existing = db.scalar(
                select(TriageRun).where(TriageRun.idempotency_key == idempotency_key)
            )
            if existing:
                if existing.result_payload:
                    return {"run_id": existing.public_id, **existing.result_payload}
                raise HTTPException(status_code=409, detail="triage_run_in_progress")

        run = TriageRun(
            request_payload=request.model_dump(),
            status="running",
            idempotency_key=idempotency_key,
            agent_version=AGENT_VERSION,
            model_name=model_identifier(),
            retrieval_version=RETRIEVAL_VERSION,
        )
        db.add(run)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            if idempotency_key:
                existing = db.scalar(
                    select(TriageRun).where(TriageRun.idempotency_key == idempotency_key)
                )
                if existing:
                    if existing.result_payload:
                        return {"run_id": existing.public_id, **existing.result_payload}
                    raise HTTPException(status_code=409, detail="triage_run_in_progress") from exc
            raise
        db.refresh(run)
        run_id = run.id
        _record_event(db, run, "run_started", {"mode": "sync"})
        db.commit()

    try:
        result = _run_graph(request, run_id)
    except Exception as exc:
        with SessionLocal() as db:
            failed = db.get(TriageRun, run_id)
            failed.status = "failed"
            failed.failure_code = "workflow_error"
            failed.error_message = "The triage workflow failed. Check the run event log."
            _record_event(db, failed, "run_failed", {"error_type": type(exc).__name__})
            db.commit()
        raise HTTPException(status_code=502, detail="triage_workflow_failed") from exc

    with SessionLocal() as db:
        saved = db.get(TriageRun, run_id)
        saved.result_payload = result
        saved.risk_level = result.get("risk_level")
        saved.status = "needs_review"
        _record_event(db, saved, "run_completed", {"tools_used": result.get("tools_used", [])})
        db.commit()
        return {"run_id": saved.public_id, **result}


@router.post("/triage-runs", status_code=status.HTTP_202_ACCEPTED, response_model=TriageRunStatus)
def create_triage_run(
    request: TriageRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    with SessionLocal() as db:
        if idempotency_key:
            existing = db.scalar(
                select(TriageRun).where(TriageRun.idempotency_key == idempotency_key)
            )
            if existing:
                return _status_payload(existing)

        run = TriageRun(
            request_payload=request.model_dump(),
            status="queued",
            idempotency_key=idempotency_key,
            agent_version=AGENT_VERSION,
            model_name=model_identifier(),
            retrieval_version=RETRIEVAL_VERSION,
        )
        db.add(run)
        db.flush()
        _record_event(db, run, "run_queued", {"mode": "worker"})
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            if idempotency_key:
                existing = db.scalar(
                    select(TriageRun).where(TriageRun.idempotency_key == idempotency_key)
                )
                if existing:
                    return _status_payload(existing)
            raise
        db.refresh(run)
        return _status_payload(run)


@router.get("/triage-runs/{run_id}", response_model=TriageRunStatus)
def get_triage_run(run_id: str):
    with SessionLocal() as db:
        run = db.scalar(select(TriageRun).where(TriageRun.public_id == run_id))
        if not run:
            raise HTTPException(status_code=404, detail="triage_run_not_found")
        return _status_payload(run)


@router.post("/triage-runs/{run_id}/approve")
def approve_triage_run(run_id: str, body: ApprovalRequest):
    with SessionLocal() as db:
        run = db.scalar(select(TriageRun).where(TriageRun.public_id == run_id))
        if not run:
            raise HTTPException(status_code=404, detail="triage_run_not_found")
        if run.status != "needs_review":
            raise HTTPException(status_code=409, detail=f"run_status_{run.status}")
        run.status = "approved"
        run.approved_work_order = body.work_order
        run.reviewer_id = body.reviewer_id
        run.approved_at = datetime.now(timezone.utc)
        _record_event(db, run, "human_approved", {"reviewer_id": body.reviewer_id})
        db.commit()
    return {"status": "approved", "run_id": run_id, "reviewer_id": body.reviewer_id}


@router.post("/triage-runs/{run_id}/reject")
def reject_triage_run(run_id: str, body: RejectionRequest):
    with SessionLocal() as db:
        run = db.scalar(select(TriageRun).where(TriageRun.public_id == run_id))
        if not run:
            raise HTTPException(status_code=404, detail="triage_run_not_found")
        if run.status != "needs_review":
            raise HTTPException(status_code=409, detail=f"run_status_{run.status}")
        run.status = "rejected"
        run.reviewer_id = body.reviewer_id
        run.error_message = body.reason
        _record_event(db, run, "human_rejected", {
            "reviewer_id": body.reviewer_id,
            "reason": body.reason,
        })
        db.commit()
    return {"status": "rejected", "run_id": run_id, "reviewer_id": body.reviewer_id}


@router.post("/triage/{run_id}/approve")
def approve_legacy_run(run_id: int, body: ApprovalRequest):
    """Backward-compatible route for the original frontend."""
    with SessionLocal() as db:
        run = db.get(TriageRun, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="triage_run_not_found")
        if run.status != "needs_review":
            raise HTTPException(status_code=409, detail=f"run_status_{run.status}")
        run.status = "approved"
        run.approved_work_order = body.work_order
        run.reviewer_id = body.reviewer_id
        run.approved_at = datetime.now(timezone.utc)
        _record_event(db, run, "human_approved", {"reviewer_id": body.reviewer_id})
        db.commit()
    return {"status": "approved", "run_id": run_id, "reviewer_id": body.reviewer_id}


@router.post("/tsb/search")
def tsb_search(body: TSBSearchRequest):
    return {"results": search_tsb_chunks(body.year, body.make, body.model, body.query, body.k)}
