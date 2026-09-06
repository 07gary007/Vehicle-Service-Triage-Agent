import json
from pathlib import Path
import httpx

BASE_URL = "http://localhost:8000"
CASES = json.loads((Path(__file__).parent / "cases.json").read_text())


def main():
    total = len(CASES)
    routing_correct = 0
    safety_total = 0
    safety_caught = 0
    complete = 0

    with httpx.Client(timeout=90.0) as client:
        for case in CASES:
            payload = {k: case[k] for k in ["vehicle", "mileage", "customer_complaint", "service_advisor_notes"]}
            response = client.post(f"{BASE_URL}/api/triage", json=payload)
            response.raise_for_status()
            result = response.json()

            expected_tools = set(case["expected_tools"])
            actual_tools = set(result.get("tools_used", []))
            if expected_tools.issubset(actual_tools):
                routing_correct += 1

            if case["expected_risk"] == "safety_review":
                safety_total += 1
                if result.get("risk_level") == "safety_review" and result.get("human_review_required"):
                    safety_caught += 1

            required = ["parsed_symptoms", "recommended_inspection_steps", "draft_work_order", "evidence_summary"]
            if all(result.get(field) for field in required):
                complete += 1

            print(case["name"], "tools=", sorted(actual_tools), "risk=", result.get("risk_level"))

    print("
Evaluation summary")
    print(f"Tool-selection coverage: {routing_correct}/{total} = {routing_correct/total:.1%}")
    if safety_total:
        print(f"Safety-escalation recall: {safety_caught}/{safety_total} = {safety_caught/safety_total:.1%}")
    print(f"Output completeness: {complete}/{total} = {complete/total:.1%}")


if __name__ == "__main__":
    main()
