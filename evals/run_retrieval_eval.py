import argparse
import json
import time
from pathlib import Path

import httpx

BASE_URL = "http://localhost:8000"
PATH = Path(__file__).parent / "retrieval_cases.json"
DEFAULT_RESULTS = Path(__file__).parent / "results" / "retrieval-latest.json"
MAX_ATTEMPTS = 8


def search_with_retry(client: httpx.Client, case: dict, base_url: str) -> httpx.Response:
    request = {key: case[key] for key in ["year", "make", "model", "query"]}
    request["k"] = 5
    last_error: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            response = client.post(f"{base_url}/api/tsb/search", json=request)
            if response.status_code < 500:
                return response
            response.raise_for_status()
        except httpx.HTTPError as exc:
            last_error = exc
            time.sleep(min(0.5 * (2**attempt), 3.0))
    raise RuntimeError("retrieval API did not become ready") from last_error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=BASE_URL)
    parser.add_argument("--cases", default=str(PATH))
    parser.add_argument("--json-out", default=str(DEFAULT_RESULTS))
    args = parser.parse_args()

    cases_path = Path(args.cases)
    if not cases_path.exists():
        raise SystemExit("retrieval_cases.json does not exist. Run backend/scripts/build_retrieval_eval.py first, then manually review the generated cases.")
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    hits = 0
    evaluated = []
    with httpx.Client(timeout=30.0) as client:
        for case in cases:
            response = search_with_retry(client, case, args.base_url)
            response.raise_for_status()
            ids = [row["document_id"] for row in response.json()["results"]]
            if case.get("expected_no_match"):
                hit = not ids
                expected = "NO_MATCH"
            else:
                expected = case["expected_document_id"]
                hit = expected in ids
            hits += int(hit)
            evaluated.append({
                "query": case["query"],
                "expected": expected,
                "actual_document_ids": ids,
                "passed": hit,
            })
            print("PASS" if hit else "FAIL", expected, "->", ids)
    metrics = {
        "cases": len(cases),
        "passed": hits,
        "accuracy_at_5": round(hits / len(cases), 4) if cases else 0.0,
        "no_match_cases": sum(case.get("expected_no_match", False) for case in cases),
    }
    report = {"metrics": metrics, "cases": evaluated}
    output_path = Path(args.json_out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Retrieval case accuracy@5: {hits}/{len(cases)} = {metrics['accuracy_at_5']:.1%}")
    print(f"JSON report: {output_path}")


if __name__ == "__main__":
    main()
