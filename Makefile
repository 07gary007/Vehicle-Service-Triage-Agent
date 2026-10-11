PYTHON := .venv/bin/python
PYTEST := .venv/bin/pytest

.PHONY: test compile lint frontend-build db-up stack-up smoke eval retrieval-eval mcp-inspect

test:
	PYTHONPATH=backend $(PYTEST)

compile:
	PYTHONPATH=backend $(PYTHON) -m compileall -q backend evals

lint:
	$(PYTHON) -m ruff check backend evals

frontend-build:
	cd frontend && npm ci && npm run build

db-up:
	docker compose up -d postgres

stack-up:
	docker compose up --build

eval:
	PYTHONPATH=backend $(PYTHON) evals/run_eval.py

retrieval-eval:
	PYTHONPATH=backend $(PYTHON) evals/run_retrieval_eval.py

smoke:
	PYTHONPATH=backend $(PYTHON) backend/scripts/smoke_stack.py

mcp-inspect:
	PYTHONPATH=. $(PYTHON) -m backend.app.mcp_server --transport stdio
