"""Add retry-safety constraints and a PostgreSQL lexical search index."""

from alembic import op
from sqlalchemy import inspect

revision = "0002_constraints_and_search"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Legacy triage rows were only created after completion, so the original
    # schema made result_payload NOT NULL. Queued worker runs need it nullable.
    op.alter_column("triage_runs", "result_payload", nullable=True)

    indexes = inspect(op.get_bind()).get_indexes("triage_runs")
    if not any(item.get("unique") and item["column_names"] == ["public_id"] for item in indexes):
        op.create_index("uq_triage_runs_public_id", "triage_runs", ["public_id"], unique=True)
    if not any(item.get("unique") and item["column_names"] == ["idempotency_key"] for item in indexes):
        op.create_index("uq_triage_runs_idempotency_key", "triage_runs", ["idempotency_key"], unique=True)

    # This index is only useful for deployments using PostgreSQL. The search
    # query still has an application-level lexical fallback for compatibility.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_tsb_chunks_search_fts "
        "ON tsb_chunks USING gin (to_tsvector('english', search_text))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_tsb_chunks_search_fts")
    op.execute("DROP INDEX IF EXISTS uq_triage_runs_idempotency_key")
    op.execute("DROP INDEX IF EXISTS uq_triage_runs_public_id")
