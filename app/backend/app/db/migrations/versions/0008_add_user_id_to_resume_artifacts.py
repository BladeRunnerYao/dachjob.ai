"""Add user_id to resume_artifacts.

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-27
"""

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE resume_artifacts ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_resume_artifacts_user_id ON resume_artifacts (user_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_resume_artifacts_job_tenant_user_created "
        "ON resume_artifacts (job_id, tenant_id, user_id, created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_resume_artifacts_job_tenant_user_created")
    op.execute("DROP INDEX IF EXISTS ix_resume_artifacts_user_id")
    op.execute("ALTER TABLE resume_artifacts DROP COLUMN IF EXISTS user_id")
