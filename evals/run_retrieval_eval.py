import json
from pathlib import Path
import httpx

BASE_URL = "http://localhost:8000"
PATH = Path(__file__).parent / "retrieval_cases.json"


def main():
    if not PATH.exists():
        raise SystemExit("retrieval_cases.json does not exist. Run backend/scripts/build_retrieval_eval.py first, then manually review the generated cases.")
    cases = json.loads(PATH.read_text())
    hits = 0
    with httpx.Client(timeout=30.0) as client:
        for case in cases:
            response = client.post(f"{BASE_URL}/api/tsb/search", json={**case, "k": 5})
            response.raise_for_status()
            ids = [row["document_id"] for row in response.json()["results"]]
            hit = case["expected_document_id"] in ids
            hits += int(hit)
            print("HIT" if hit else "MISS", case["expected_document_id"], "->", ids)
    print(f"Recall@5: {hits}/{len(cases)} = {hits/len(cases):.1%}")


if __name__ == "__main__":
    main()
