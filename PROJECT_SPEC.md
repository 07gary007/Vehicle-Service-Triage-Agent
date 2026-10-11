# Vehicle Service Triage Agent — Product / Engineering Spec

## Product definition

A service-advisor copilot that converts natural-language vehicle concerns into an evidence-grounded triage workflow. It parses the concern, applies a safety policy, retrieves official recalls and technical communications, reviews prior service history, drafts technician inspection steps, and pauses for human approval.

## Primary user

Dealership service advisor / maintenance coordinator.

## Agent boundary

The system is an evidence-gathering and drafting agent, not an autonomous diagnostician. The LLM may plan evidence collection and synthesize supplied evidence, but it must not:

- claim a failed part without supporting evidence;
- authorize a repair;
- override deterministic safety escalation;
- hide missing, conflicting, or failed evidence;
- write an approved work order without a human reviewer.

## Workflow

```text
validate input
  -> deterministic safety gate
  -> structured concern analysis
  -> evidence retrieval through MCP tools
  -> evidence sufficiency / abstention check
  -> draft inspection steps and work order
  -> human review
  -> approve or reject with audit event
```

## External tool contract

The independent MCP server exposes read-only tools:

1. `search_recalls`
2. `search_technical_communications`
3. `get_service_history`

Each tool returns status, items, source metadata, and evidence snippets. The application API owns approval and write operations.

## Persistence

The system stores:

- request and result payloads;
- public run ID and idempotency key;
- workflow status and risk level;
- agent/model/retrieval versions;
- tool and lifecycle events;
- reviewer identity, approval timestamp, and final work order;
- failure state without exposing provider exception details to clients.

## Retrieval requirements

- exact vehicle-year filtering when available;
- conservative query expansion for customer language;
- vector and lexical relevance signals;
- document-level deduplication;
- evidence threshold and abstention;
- source ID, URL, section/page metadata when available;
- reviewed retrieval evaluation set.

## Data scope

The current checked-in dataset contains synthetic dealership history and a controlled NHTSA ingestion path for the demo vehicle families. The architecture must report unsupported vehicles and missing full documents explicitly rather than imply broad coverage.

## Deployment target

Local Docker Compose is the reference development topology. The services must
remain deployable as independent containers so the same system can later run on
Azure Container Apps, Google Cloud Run, or another managed container platform.
An Azure deployment can add managed Postgres/pgvector, Blob Storage, Key Vault,
Entra identity, CI/CD, and application telemetry; these are deployment adapters,
not dependencies of the core workflow.

## Evaluation

- safety false-negative rate;
- tool-selection precision and recall;
- retrieval Recall@5, MRR, and nDCG;
- citation correctness and grounded recommendation rate;
- abstention precision;
- end-to-end task success;
- p50/p95 latency and cost per run;
- tool/provider failure rate;
- reviewer edit distance and approval rate.
