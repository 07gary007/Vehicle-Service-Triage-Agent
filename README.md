# Vehicle Service Triage Agent

An evidence-grounded service-advisor copilot for automotive intake triage. It converts a customer complaint into a safety-aware investigation, gathers recall / technical-communication / service-history evidence, drafts technician inspection steps, and pauses for human approval before a work order is accepted.

This repository is intentionally built as a production-oriented portfolio project rather than an autonomous vehicle-diagnosis demo.

## What this project demonstrates

- LangGraph workflow orchestration with structured LLM outputs and bounded tool use
- A separately deployable MCP server exposing domain tools to any MCP client
- Hybrid retrieval with deterministic query expansion, vector similarity, lexical overlap, metadata filtering, deduplication, and abstention
- Evidence provenance: source IDs, source URLs, retrieval scores, snippets, and ingestion versions
- Safety routing that fails closed on safety signals, weak evidence, or tool failures
- Durable triage runs with public IDs, idempotency keys, worker processing, approval/rejection states, and event audit records
- FastAPI APIs, Postgres/pgvector persistence, Docker Compose, Alembic migrations, and CI checks
- Evaluation hooks for routing coverage, safety escalation, retrieval Recall@5, and output completeness

## Architecture

```text
Service advisor UI
        |
        v
FastAPI API  ---->  PostgreSQL / triage runs / audit events
        |
        v
Postgres-backed worker
        |
        v
LangGraph triage workflow
        |
        v
MCP client adapter
        |
        v
Remote MCP server
  - search_recalls
  - search_technical_communications
  - get_service_history
        |
        +--> NHTSA Recalls API
        +--> PostgreSQL + pgvector
        +--> dealership service history
```

The MCP server exposes read-only evidence tools. Work-order approval remains an application-level human action rather than a model-controlled tool call.

## Data boundary

Real public data:

- NHTSA Recalls API
- NHTSA manufacturer-communication bulk export

Synthetic data:

- dealership service history in `backend/scripts/seed_service_history.py`

The repository does not claim to have access to private dealership CRM data. The MCP contract is designed so the synthetic adapter can later be replaced by an authenticated dealership connector.

## Local development

Requirements: Docker Desktop, Python 3.13+, Node 22+, and an OpenAI-compatible API key.

```bash
cp .env.example .env
# Add OPENAI_API_KEY to .env

python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

docker compose up -d postgres
python backend/scripts/seed_service_history.py
python backend/scripts/ingest_nhtsa_tsb.py --clear --max-docs-per-vehicle 150
```

### Model providers

OpenAI is the default provider for local development. The application keeps the
model boundary provider-neutral so the same workflow can later use Azure OpenAI
without changing the LangGraph or MCP code:

```text
MODEL_PROVIDER=openai
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-5.6-luna
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_USE_RESPONSES_API=true
```

For Azure OpenAI, set `MODEL_PROVIDER=azure_openai`, an endpoint, deployment
names, and either `AZURE_OPENAI_API_KEY` or
`AZURE_OPENAI_USE_MANAGED_IDENTITY=true`. In Azure, managed identity is the
preferred authentication path; the API-key path is useful for local smoke
testing. Chat and embedding deployment names are intentionally separate because
Azure deployments are named independently from their underlying model names.

The OpenAI Responses API is enabled by default because reasoning-capable models
may reject function tools through the legacy Chat Completions path. Azure keeps
its own switch because Responses API availability depends on the Azure model
deployment and API version.

The Postgres vector column currently uses 1536 dimensions. If the embedding
deployment changes dimensions, the index must be migrated and all TSB documents
must be re-ingested; changing the chat model alone does not require re-ingestion.

For the simple local mode, run the API and frontend separately:

```bash
uvicorn backend.app.main:app --reload --port 8000

cd frontend
npm install
npm run dev
```

Local mode calls the domain services directly:

```text
AGENT_TOOL_MODE=local
```

To run the complete containerized path, including the remote MCP boundary and worker:

```bash
docker compose up --build
```

The full stack exposes:

- UI: `http://localhost:5173`
- API: `http://localhost:8000`
- MCP endpoint: `http://localhost:8001/mcp`
- API liveness: `http://localhost:8000/api/health`
- API readiness: `http://localhost:8000/api/ready`

The Compose backend uses `AGENT_TOOL_MODE=mcp`, so the LangGraph agent is exercised through the separately running MCP server rather than only through local Python functions.

## API workflow

Synchronous compatibility endpoint for local evaluation:

```text
POST /api/triage
```

Production-oriented queued workflow:

```text
POST /api/triage-runs                 -> 202 + queued run
GET  /api/triage-runs/{run_id}        -> status/result
POST /api/triage-runs/{run_id}/approve
POST /api/triage-runs/{run_id}/reject
```

The `Idempotency-Key` header can be used to safely retry run creation. The worker claims queued runs using PostgreSQL row locking, records lifecycle events, and persists failures without returning provider exception details to the client.

## MCP server

Run it over stdio for local MCP inspection:

```bash
PYTHONPATH=. .venv/bin/python -m backend.app.mcp_server --transport stdio
```

Run it over Streamable HTTP:

```bash
PYTHONPATH=. .venv/bin/python -m backend.app.mcp_server \
  --transport streamable-http --host 0.0.0.0 --port 8001
```

Available tools:

- `search_recalls(year, make, model, symptoms)`
- `search_technical_communications(year, make, model, query, k)`
- `get_service_history(vehicle_id, limit)`

Set `MCP_API_KEY` for the demo header-based guard when running the endpoint directly. In Azure, use Entra authentication and gateway policy rather than relying on this simple local guard.

## Retrieval design

The retrieval pipeline intentionally separates deterministic vehicle filtering from semantic matching:

1. Normalize the complaint without changing the reported facts.
2. Add conservative symptom paraphrases such as `shake -> vibration` and `highway -> high speed`.
3. Retrieve exact vehicle-year candidates with pgvector.
4. Fall back to same-model family evidence only when exact-year data is unavailable.
5. Combine vector similarity and lexical overlap.
6. Deduplicate at document level.
7. Abstain when the evidence threshold is not met.
8. Return source metadata with every evidence item.

The current NHTSA bulk export can provide concise summaries rather than full bulletin bodies. The ingestion code preserves that limitation instead of pretending that a summary is a complete long bulletin. A future production connector should ingest full manufacturer documents with section/page metadata when those documents are legitimately available.

## Evaluation

Run deterministic checks:

```bash
make compile
make test
```

Run a no-LLM stack smoke check against the running Docker Compose services:

```bash
make smoke
```

This verifies API liveness/readiness and that an external MCP client can
initialize the remote server and discover all three domain tools. It does not
consume model tokens.

Run the end-to-end smoke evaluation while the API is running:

```bash
make eval
```

The end-to-end evaluator uses the reviewed cases in `evals/cases.json` and
writes a machine-readable report to `evals/results/latest.json`. It measures
risk accuracy, human-review accuracy, tool coverage, output completeness, and
safety-review recall. It invokes the configured model provider, so run it only
when model usage is intentional.

For retrieval evaluation:

```bash
python backend/scripts/build_retrieval_eval.py --count 30
# Manually review evals/retrieval_cases.json
make retrieval-eval
```

The repository includes a small manually reviewed retrieval set in
`evals/retrieval_cases.json`, including a negative A/C case that should abstain
instead of returning an unrelated bulletin. Generated retrieval cases are not
treated as resume-quality ground truth until manually reviewed. The checked-in
cases are still an engineering smoke benchmark; expand them before reporting
retrieval numbers on a resume, and add citation correctness, latency, tool
failures, and grounded inspection recommendations.

## Production deployment direction

The repository includes a local container topology, migration workflow, and
provider-neutral model boundary. The local Docker Compose topology is the
reference development environment; a public deployment is an optional next
step, not a prerequisite for the agent design.

A realistic Azure deployment would map the components as follows:

- API and MCP containers: Azure Container Apps
- Worker: Container Apps Job or a Service Bus-backed worker
- Database: Azure Database for PostgreSQL with pgvector
- Raw documents: Azure Blob Storage
- Model access: Azure OpenAI / Microsoft Foundry
- Secrets and identity: Key Vault + Managed Identity / Entra ID
- Observability: Application Insights + OpenTelemetry
- Infrastructure: Bicep or Azure Developer CLI

The same container boundary can also be deployed to a serverless container
platform such as Google Cloud Run. The important design decision is keeping the
API, worker, MCP server, database, model provider, and secret boundary explicit;
the cloud vendor is an adapter around that boundary.

Databricks is deliberately not required for the current workload. It becomes reasonable when the system grows into large-scale multi-source ingestion, lakehouse governance, or batch analytics.

## Safety boundary

This system is a decision-support copilot. It does not autonomously diagnose a failed component, authorize a repair, adjudicate warranty, or tell a customer to perform a repair. Safety-related complaints, weak evidence, conflicting evidence, and tool failures require human review.
