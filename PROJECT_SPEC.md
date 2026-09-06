# Vehicle Service Triage Agent — Product / R&D Spec

## Product definition
A service-advisor copilot that converts natural-language vehicle concerns into an evidence-grounded triage workflow. It parses the issue, checks safety risk, uses tools to search NHTSA recalls, retrieves relevant manufacturer technical communications through RAG, reviews synthetic dealership service history, and drafts a work order for human approval.

## User
Dealership service advisor / maintenance coordinator.

## Why this is an agent rather than a PDF chatbot
The system maintains shared state and can select among structured external data, semantic retrieval, and internal history. It routes safety-sensitive cases to human review and produces a work-order artifact rather than a free-form answer.

## Structured input
- vehicle year / make / model / optional demo vehicle ID
- mileage
- customer complaint
- advisor notes

## Structured output
- risk level
- parsed symptoms
- matched recalls
- matched technical communications
- prior service context
- recommended technician inspection steps
- human-review flag
- draft work order

## LangGraph state
- request
- concern_analysis
- messages / tool trace
- result

## Core tools
1. NHTSA recall search
2. pgvector RAG over NHTSA manufacturer technical communications
3. dealership service-history lookup

## Guardrail
The product performs intake triage and evidence collection, not autonomous diagnosis or repair authorization. Safety-related complaints force human review.

## Evaluation
- Tool-selection coverage
- Safety-escalation recall
- TSB Recall@5 on a manually reviewed retrieval set
- Output completeness / end-to-end task success

## Scope deliberately excluded from v1
- multi-agent architecture
- MCP
- voice
- autonomous repair decisions
- warranty adjudication
- live dealership integrations
