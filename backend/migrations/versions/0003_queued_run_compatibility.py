"""Make legacy result payloads nullable for queued worker runs."""

from alembic import op

revision = "0003_queued_run_compatibility"
down_revision = "0002_constraints_and_search"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("triage_runs", "result_payload", nullable=True)


def downgrade() -> None:
    op.alter_column("triage_runs", "result_payload", nullable=False)

