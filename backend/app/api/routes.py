from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ..agent.graph import triage_graph
from ..db import SessionLocal
from ..models import TriageRun
from ..schemas import ApprovalRequest, TriageRequest, TSBSearchRequest
from ..services.retrieval import search_tsb_chunks

router = APIRouter(prefix="/api")


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/triage")
def triage(request: TriageRequest):
    try:
        output = triage_graph.invoke({"request": request.model_dump(), "messages": []}, config={"recursion_limit": 12})
        result = output["result"]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    with SessionLocal() as db:
        run = TriageRun(request_payload=request.model_dump(), result_payload=result, status="needs_review")
        db.add(run)
        db.commit()
        db.refresh(run)
    return {"run_id": run.id, **result}


@router.post("/triage/{run_id}/approve")
def approve(run_id: int, body: ApprovalRequest):
    with SessionLocal() as db:
        run = db.scalar(select(TriageRun).where(TriageRun.id == run_id))
        if not run:
            raise HTTPException(status_code=404, detail="Triage run not found")
        run.status = "approved"
        run.approved_work_order = body.work_order
        db.commit()
    return {"status": "approved", "run_id": run_id}


@router.post("/tsb/search")
def tsb_search(body: TSBSearchRequest):
    return {"results": search_tsb_chunks(body.year, body.make, body.model, body.query, body.k)}
