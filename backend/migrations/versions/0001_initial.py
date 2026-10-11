"""Initial production-oriented schema, including a safe legacy upgrade path.

Revision ID: 0001_initial
"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy import inspect

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def table_exists(name: str) -> bool:
    return name in inspect(op.get_bind()).get_table_names()


def column_exists(table: str, column: str) -> bool:
    return column in {item["name"] for item in inspect(op.get_bind()).get_columns(table)}


def add_column_if_missing(table: str, column: sa.Column) -> None:
    if not column_exists(table, column.name):
        op.add_column(table, column)


def index_if_missing(name: str, table: str, columns: list[str]) -> None:
    if name not in {item["name"] for item in inspect(op.get_bind()).get_indexes(table)}:
        op.create_index(name, table, columns)


def unique_index_if_missing(name: str, table: str, columns: list[str]) -> None:
    indexes = inspect(op.get_bind()).get_indexes(table)
    if not any(item["unique"] and item["column_names"] == columns for item in indexes):
        op.create_index(name, table, columns, unique=True)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    if not table_exists("service_records"):
        op.create_table(
            "service_records",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("vehicle_id", sa.String(length=64), nullable=False),
            sa.Column("model_year", sa.Integer(), nullable=False),
            sa.Column("make", sa.String(length=64), nullable=False),
            sa.Column("model", sa.String(length=128), nullable=False),
            sa.Column("mileage", sa.Integer(), nullable=False),
            sa.Column("service_date", sa.Date(), nullable=False),
            sa.Column("category", sa.String(length=128), nullable=False),
            sa.Column("technician_note", sa.Text(), nullable=False),
        )
    for column in ["vehicle_id", "model_year", "make", "model"]:
        index_if_missing(f"ix_service_records_{column}", "service_records", [column])

    if not table_exists("tsb_chunks"):
        op.create_table(
            "tsb_chunks",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("nhtsa_id", sa.String(length=64), nullable=False),
            sa.Column("document_id", sa.String(length=160), nullable=False),
            sa.Column("make", sa.String(length=64), nullable=False),
            sa.Column("model", sa.String(length=128), nullable=False),
            sa.Column("model_year", sa.Integer(), nullable=False),
            sa.Column("component", sa.String(length=256), nullable=False, server_default=""),
            sa.Column("communication_type", sa.String(length=128), nullable=False, server_default=""),
            sa.Column("summary", sa.Text(), nullable=False),
            sa.Column("chunk_text", sa.Text(), nullable=False),
            sa.Column("search_text", sa.Text(), nullable=False, server_default=""),
            sa.Column("source_url", sa.Text(), nullable=True),
            sa.Column("section_title", sa.String(length=256), nullable=False, server_default=""),
            sa.Column("page_number", sa.Integer(), nullable=True),
            sa.Column("ingestion_version", sa.String(length=64), nullable=False, server_default="v1"),
            sa.Column("embedding", Vector(1536), nullable=False),
        )
    else:
        add_column_if_missing("tsb_chunks", sa.Column("search_text", sa.Text(), nullable=True))
        add_column_if_missing("tsb_chunks", sa.Column("source_url", sa.Text(), nullable=True))
        add_column_if_missing("tsb_chunks", sa.Column("section_title", sa.String(256), nullable=True))
        add_column_if_missing("tsb_chunks", sa.Column("page_number", sa.Integer(), nullable=True))
        add_column_if_missing("tsb_chunks", sa.Column("ingestion_version", sa.String(64), nullable=True))
        op.execute(
            "UPDATE tsb_chunks SET search_text = COALESCE(component, '') || ' ' || "
            "COALESCE(summary, '') || ' ' || COALESCE(chunk_text, '') "
            "WHERE search_text IS NULL"
        )
        op.execute("UPDATE tsb_chunks SET section_title = '' WHERE section_title IS NULL")
        op.execute("UPDATE tsb_chunks SET ingestion_version = 'legacy-v1' WHERE ingestion_version IS NULL")
    for column in ["nhtsa_id", "document_id", "make", "model", "model_year"]:
        index_if_missing(f"ix_tsb_chunks_{column}", "tsb_chunks", [column])

    if not table_exists("triage_runs"):
        op.create_table(
            "triage_runs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("public_id", sa.String(length=36), nullable=False),
            sa.Column("idempotency_key", sa.String(length=128), nullable=True),
            sa.Column("request_payload", sa.JSON(), nullable=False),
            sa.Column("result_payload", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="needs_review"),
            sa.Column("risk_level", sa.String(length=32), nullable=True),
            sa.Column("approved_work_order", sa.Text(), nullable=True),
            sa.Column("reviewer_id", sa.String(length=128), nullable=True),
            sa.Column("failure_code", sa.String(length=64), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("agent_version", sa.String(length=64), nullable=False, server_default="unknown"),
            sa.Column("model_name", sa.String(length=128), nullable=False, server_default="unknown"),
            sa.Column("retrieval_version", sa.String(length=64), nullable=False, server_default="unknown"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint("public_id"),
            sa.UniqueConstraint("idempotency_key"),
        )
    else:
        add_column_if_missing("triage_runs", sa.Column("public_id", sa.String(36), nullable=True))
        add_column_if_missing("triage_runs", sa.Column("idempotency_key", sa.String(128), nullable=True))
        add_column_if_missing("triage_runs", sa.Column("risk_level", sa.String(32), nullable=True))
        add_column_if_missing("triage_runs", sa.Column("reviewer_id", sa.String(128), nullable=True))
        add_column_if_missing("triage_runs", sa.Column("failure_code", sa.String(64), nullable=True))
        add_column_if_missing("triage_runs", sa.Column("error_message", sa.Text(), nullable=True))
        add_column_if_missing("triage_runs", sa.Column("agent_version", sa.String(64), nullable=True))
        add_column_if_missing("triage_runs", sa.Column("model_name", sa.String(128), nullable=True))
        add_column_if_missing("triage_runs", sa.Column("retrieval_version", sa.String(64), nullable=True))
        add_column_if_missing("triage_runs", sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
        add_column_if_missing("triage_runs", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
        op.execute("UPDATE triage_runs SET public_id = md5(id::text || '-legacy') WHERE public_id IS NULL")
        op.execute("UPDATE triage_runs SET agent_version = 'legacy-v1' WHERE agent_version IS NULL")
        op.execute("UPDATE triage_runs SET model_name = 'unknown' WHERE model_name IS NULL")
        op.execute("UPDATE triage_runs SET retrieval_version = 'legacy-v1' WHERE retrieval_version IS NULL")
        op.alter_column("triage_runs", "public_id", nullable=False)
    index_if_missing("ix_triage_runs_public_id", "triage_runs", ["public_id"])
    unique_index_if_missing("uq_triage_runs_public_id", "triage_runs", ["public_id"])
    unique_index_if_missing("uq_triage_runs_idempotency_key", "triage_runs", ["idempotency_key"])

    if not table_exists("triage_events"):
        op.create_table(
            "triage_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("run_id", sa.Integer(), sa.ForeignKey("triage_runs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("event_type", sa.String(length=64), nullable=False),
            sa.Column("node_name", sa.String(length=128), nullable=True),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
    index_if_missing("ix_triage_events_run_id", "triage_events", ["run_id"])
    index_if_missing("ix_triage_events_event_type", "triage_events", ["event_type"])


def downgrade() -> None:
    op.drop_table("triage_events")
    op.drop_table("triage_runs")
    op.drop_table("tsb_chunks")
    op.drop_table("service_records")
