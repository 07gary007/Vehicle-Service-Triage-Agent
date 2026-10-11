import argparse
import json
import random
import sys
from pathlib import Path

from sqlalchemy import select

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import SessionLocal
from app.models import TSBChunk
from app.services.llm import get_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel


class EvalQuery(BaseModel):
    query: str


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=30)
    parser.add_argument("--out", default=str(Path(__file__).resolve().parents[2] / "evals" / "retrieval_cases.json"))
    args = parser.parse_args()

    with SessionLocal() as db:
        rows = db.scalars(select(TSBChunk)).all()
    unique = {}
    for row in rows:
        unique[(row.document_id, row.make, row.model, row.model_year)] = row
    samples = random.sample(list(unique.values()), min(args.count, len(unique)))

    llm = get_chat_model().with_structured_output(EvalQuery)
    cases = []
    for row in samples:
        prompt = f"""Vehicle: {row.model_year} {row.make} {row.model}
Manufacturer communication summary: {row.summary}
Write one short realistic service-advisor search query that paraphrases the symptom/condition without repeating the bulletin ID. Do not add facts not in the summary."""
        generated = llm.invoke([
            SystemMessage(content="Generate a retrieval-evaluation query from the supplied source only."),
            HumanMessage(content=prompt),
        ])
        cases.append({
            "year": row.model_year,
            "make": row.make,
            "model": row.model,
            "query": generated.query,
            "expected_document_id": row.document_id,
            "manual_review_required": True,
        })

    Path(args.out).write_text(json.dumps(cases, indent=2), encoding="utf-8")
    print(f"Wrote {len(cases)} retrieval cases to {args.out}. Manually review them before using the metric in a resume.")


if __name__ == "__main__":
    main()
