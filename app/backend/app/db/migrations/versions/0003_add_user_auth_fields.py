"""Add password_hash and google_id to users.

Revision ID: 0003_add_user_auth_fields
Revises: 0002_job_import_metadata
Create Date: 2026-05-23
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_add_user_auth_fields"
down_revision = "0002_job_import_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("google_id", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "google_id")
    op.drop_column("users", "password_hash")
