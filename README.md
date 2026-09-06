# Vehicle Service Triage Agent

A portfolio-grade AI Engineer project: a dealership service-advisor copilot that turns a natural-language vehicle concern into an evidence-grounded triage workflow using **LangGraph, tool invocation, RAG, structured outputs, persistent service context, safety routing, and human approval**.

## Architecture

```text
Customer concern
      ↓
Structured concern analysis
      ↓
LangGraph investigation agent
  ├── NHTSA recall tool
  ├── TSB / manufacturer-communication RAG tool (PostgreSQL + pgvector)
  └── dealership service-history tool
      ↓
Evidence-grounded inspection steps
      ↓
Draft work order
      ↓
Service advisor edits / approves
```

The system intentionally separates deterministic operational facts from unstructured semantic retrieval:
- recalls + service history → structured tool queries
- manufacturer technical communications → vector retrieval

## Real vs synthetic data

**Real public data**
- NHTSA Recalls API
- NHTSA Manufacturer Communications / TSB bulk files

**Synthetic data**
- dealership-specific prior service records, because real dealer CRM/service-history data is private

NHTSA documents the recalls API and manufacturer-communications downloads on its official datasets page.

## Requirements

- Docker Desktop (simplest way to run PostgreSQL + pgvector)
- Python 3.11+
- Node 20+
- an OpenAI API key

## 1. Environment

From the repository root:

```bash
cp .env.example .env
```

Add your key to `.env`:

```text
OPENAI_API_KEY=...
```

The sample config uses `gpt-5.6-luna` for the agent and `text-embedding-3-small` for embeddings. You can change either through `.env`.

## 2. Start PostgreSQL + pgvector

```bash
docker compose up -d
```

## 3. Backend

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

Seed the synthetic dealership history:

```bash
python backend/scripts/seed_service_history.py
```

Download and ingest a controlled subset of official NHTSA manufacturer communications for Honda Civic and Toyota RAV4, model years 2020–2024:

```bash
python backend/scripts/ingest_nhtsa_tsb.py --clear --max-docs-per-vehicle 150
```

This script downloads the official NHTSA ZIPs itself. You do **not** need to manually download a dataset.

Start the API:

```bash
uvicorn backend.app.main:app --reload --port 8000
```

Health check:

```bash
curl http://localhost:8000/api/health
```

## 4. Frontend

Open a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

The UI includes two seeded demo vehicles:
- `HC-2021-001` — 2021 Honda Civic
- `TR-2022-002` — 2022 Toyota RAV4

## 5. Evaluation

Start with the small checked-in smoke set:

```bash
python evals/run_eval.py
```

It measures:
- expected-tool coverage
- safety-escalation recall
- output completeness

For a real RAG metric, generate retrieval cases from ingested NHTSA source records:

```bash
python backend/scripts/build_retrieval_eval.py --count 30
```

**Manually review** `evals/retrieval_cases.json` before reporting any metric. Then run:

```bash
python evals/run_retrieval_eval.py
```

This reports Recall@5 against the source document IDs.

Before putting a number on a resume, expand the triage set toward ~80 cases and manually validate the expected labels. Do not report generated-but-unreviewed evaluation labels.

## API request example

```json
{
  "vehicle": {
    "year": 2021,
    "make": "Honda",
    "model": "Civic",
    "vehicle_id": "HC-2021-001"
  },
  "mileage": 52100,
  "customer_complaint": "Grinding noise when braking and the ABS light came on yesterday.",
  "service_advisor_notes": "Customer says braking feel may be slightly different."
}
```

## What to say in an AI Engineer interview

**Why LangGraph?** The investigation has shared state, conditional tool use, safety routing, a tool loop, and a human-review boundary. A single prompt chain makes those transitions and failure boundaries harder to inspect.

**Why not put everything in a vector database?** Vehicle identifiers, mileage, recall campaign IDs, and service dates are deterministic structured facts. Semantic retrieval is reserved for unstructured manufacturer communications and technician notes.

**Why human-in-the-loop?** The product is a decision-support tool. It must not autonomously diagnose safety-critical faults or authorize repairs.

**How is it evaluated?** Tool routing, safety escalation, retrieval Recall@5, and end-to-end output completeness/task success are measured separately so a good final answer cannot hide a bad retrieval or routing step.

## Resume shape after the metrics are real

Do not copy numbers until you run and review the evals.

- Built an AI service-triage agent for automotive service advisors to investigate customer concerns across manufacturer technical communications, safety recalls, and prior dealership service records.
- Orchestrated a LangGraph workflow combining constrained tool invocation, pgvector RAG, persistent service context, safety-aware routing, structured outputs, and human-approved work-order generation.
- Evaluated the system on **X** reviewed service cases, reaching **X%** TSB Recall@5, **X%** safety-escalation recall, and **X%** end-to-end task success.
