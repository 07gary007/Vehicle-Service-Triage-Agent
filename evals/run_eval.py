"""Run the reviewed end-to-end triage evaluation set.

This script intentionally calls the running API, so it can exercise the same
MCP boundary and worker/API contract used by the demo. It is opt-in because
triage cases invoke the configured model provider and may incur model costs.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

import httpx

DEFAULT_CASES = Path(__file__).with_name("cases.json")
DEFAULT_RESULTS = Path(__file__).with_name("results") / "latest.json"


def evaluate_case(case: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    expected_tools = set(case["expected_tools"])
    actual_tools = set(result.get("tools_used", []))
    required_fields = [
        "parsed_symptoms",
        "recommended_inspection_steps",
        "draft_work_order",
        "evidence_summary",
    ]
    complete = all(result.get(field) for field in required_fields)
    evidence = result.get("evidence", [])
    risk_correct = result.get("risk_level") == case["expected_risk"]
    human_review_correct = result.get("human_review_required") == case["expected_human_review"]
    return {
        "name": case["name"],
        "risk_correct": risk_correct,
        "expected_risk": case["expected_risk"],
        "actual_risk": result.get("risk_level"),
        "human_review_correct": human_review_correct,
        "expected_human_review": case["expected_human_review"],
        "actual_human_review": result.get("human_review_required"),
        "tool_coverage": expected_tools.issubset(actual_tools),
        "expected_tools": sorted(expected_tools),
        "actual_tools": sorted(actual_tools),
        "complete_output": complete,
        "evidence_count": len(evidence),
        "run_id": result.get("run_id"),
    }


def ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.getenv("TRIAGE_BASE_URL", "http://localhost:8000"))
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument("--json-out", default=str(DEFAULT_RESULTS))
    parser.add_argument("--timeout", type=float, default=90.0)
    args = parser.parse_args()

    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    evaluated: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    with httpx.Client(timeout=args.timeout) as client:
        for case in cases:
            payload = {
                key: case[key]
                for key in ["vehicle", "mileage", "customer_complaint", "service_advisor_notes"]
            }
            headers = {"Idempotency-Key": f"eval-{case['name']}-{time.time_ns()}"}
            try:
                response = client.post(f"{args.base_url}/api/triage", json=payload, headers=headers)
                response.raise_for_status()
                result = response.json()
                row = evaluate_case(case, result)
                evaluated.append(row)
                print(
                    case["name"],
                    f"risk={'PASS' if row['risk_correct'] else 'FAIL'}",
                    f"review={'PASS' if row['human_review_correct'] else 'FAIL'}",
                    f"tools={'PASS' if row['tool_coverage'] else 'FAIL'}",
                    f"evidence={row['evidence_count']}",
                )
            except Exception as exc:  # keep the report useful when one case fails
                row = {"name": case["name"], "error_type": type(exc).__name__, "error": str(exc)}
                failures.append(row)
                print(case["name"], "ERROR", type(exc).__name__)

    total = len(cases)
    safety_cases = [row for row in evaluated if row["expected_risk"] == "safety_review"]
    metrics = {
        "cases": total,
        "completed_cases": len(evaluated),
        "failed_cases": len(failures),
        "risk_accuracy": ratio(sum(row["risk_correct"] for row in evaluated), len(evaluated)),
        "human_review_accuracy": ratio(
            sum(row["human_review_correct"] for row in evaluated), len(evaluated)
        ),
        "tool_coverage": ratio(sum(row["tool_coverage"] for row in evaluated), len(evaluated)),
        "output_completeness": ratio(sum(row["complete_output"] for row in evaluated), len(evaluated)),
        "safety_review_recall": ratio(
            sum(
                row["actual_human_review"] is True and row["actual_risk"] == "safety_review"
                for row in safety_cases
            ),
            len(safety_cases),
        ),
    }
    report = {"metrics": metrics, "cases": evaluated, "failures": failures}
    output_path = Path(args.json_out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("\nEvaluation summary")
    for key, value in metrics.items():
        print(f"{key}: {value}")
    print(f"JSON report: {output_path}")


if __name__ == "__main__":
    main()
