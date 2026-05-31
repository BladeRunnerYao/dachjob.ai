"""Add persisted job labels.

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-31
"""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "job_postings",
        sa.Column("saved", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column("job_postings", sa.Column("application_status", sa.Text(), nullable=True))

    op.execute("UPDATE job_postings SET saved = TRUE WHERE status = 'saved'")
    op.execute("UPDATE job_postings SET application_status = 'applied' WHERE status = 'applied'")
    op.execute("UPDATE job_postings SET status = 'new' WHERE status IN ('saved', 'applied')")

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_job_postings_tenant_saved ON job_postings (tenant_id, saved)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_job_postings_tenant_application_status "
        "ON job_postings (tenant_id, application_status)"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE job_postings SET status = 'applied' "
        "WHERE application_status IN ('applied', 'interview', 'rejected', 'offer')"
    )
    op.execute("UPDATE job_postings SET status = 'saved' WHERE saved = TRUE")
    op.execute("DROP INDEX IF EXISTS ix_job_postings_tenant_application_status")
    op.execute("DROP INDEX IF EXISTS ix_job_postings_tenant_saved")
    op.drop_column("job_postings", "application_status")
    op.drop_column("job_postings", "saved")
