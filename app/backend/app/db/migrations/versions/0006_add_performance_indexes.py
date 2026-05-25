"""Add performance indexes for job detail queries.

Add composite indexes on match_reports, resume_artifacts, and evidence_chunks
to fix N+1 and sequential scan query performance.

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-25
"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
        "ix_match_reports_job_id_tenant_id_created "
        "ON match_reports (job_id, tenant_id, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
        "ix_resume_artifacts_job_id_tenant_id_created "
        "ON resume_artifacts (job_id, tenant_id, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
        "ix_evidence_chunks_profile_id "
        "ON evidence_chunks (profile_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_match_reports_job_id_tenant_id_created")
    op.execute("DROP INDEX IF EXISTS ix_resume_artifacts_job_id_tenant_id_created")
    op.execute("DROP INDEX IF EXISTS ix_evidence_chunks_profile_id")
