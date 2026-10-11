"""PostgreSQL-backed triage worker.

This is intentionally small and inspectable for a portfolio project. A cloud
deployment can later replace the polling loop with Service Bus while keeping
the same run state and workflow contract.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from sqlalchemy import select

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.agent.graph import AGENT_VERSION, RETRIEVAL_VERSION, triage_graph  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.models import TriageEvent, TriageRun  # noqa: E402
from app.schemas import TriageRequest  # noqa: E402
from app.services.llm import model_identifier  # noqa: E402


def record_event(db, run: TriageRun, event_type: str, payload: dict) -> None:
    db.add(TriageEvent(run_id=run.id, event_type=event_type, payload=payload))


def claim_one() -> int | None:
    with SessionLocal() as db:
        run = db.scalar(
            select(TriageRun)
            .where(TriageRun.status == "queued")
            .order_by(TriageRun.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if not run:
            return None
        run.status = "running"
        record_event(db, run, "run_started", {"mode": "worker"})
        db.commit()
        return run.id


def process(run_id: int) -> None:
    with SessionLocal() as db:
        run = db.get(TriageRun, run_id)
        if not run:
            return
        request = TriageRequest.model_validate(run.request_payload)

    try:
        output = triage_graph.invoke(
            {"request": request.model_dump(), "messages": []},
            config={
                "recursion_limit": get_settings().max_triage_recursion,
                "configurable": {"thread_id": run_id},
            },
        )
        result = output["result"]
    except Exception as exc:
        with SessionLocal() as db:
            run = db.get(TriageRun, run_id)
            run.status = "failed"
            run.failure_code = "workflow_error"
            run.error_message = "The triage workflow failed. Check the run event log."
            record_event(db, run, "run_failed", {"error_type": type(exc).__name__})
            db.commit()
        return

    with SessionLocal() as db:
        run = db.get(TriageRun, run_id)
        run.result_payload = result
        run.risk_level = result.get("risk_level")
        run.status = "needs_review"
        run.agent_version = AGENT_VERSION
        run.model_name = model_identifier()
        run.retrieval_version = RETRIEVAL_VERSION
        record_event(db, run, "run_completed", {"tools_used": result.get("tools_used", [])})
        db.commit()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    args = parser.parse_args()

    if get_settings().auto_create_schema:
        Base.metadata.create_all(bind=engine)

    while True:
        run_id = claim_one()
        if run_id is not None:
            process(run_id)
        elif args.once:
            return
        else:
            time.sleep(args.poll_seconds)


if __name__ == "__main__":
    main()
