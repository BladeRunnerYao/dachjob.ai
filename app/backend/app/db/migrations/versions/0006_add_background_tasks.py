"""Add background_tasks table.

Revision ID: 0006_add_background_tasks
Revises: 0005_add_user_id_to_candidate_profiles
Create Date: 2026-05-25
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "background_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
            index=True,
        ),
        sa.Column("kind", sa.String(80), nullable=False, index=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued", index=True),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("celery_task_id", sa.String(255), nullable=True, index=True),
        sa.Column("idempotency_key", sa.String(255), nullable=True, index=True),
        sa.Column("payload_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("result_json", postgresql.JSONB(), nullable=True),
        sa.Column("error_json", postgresql.JSONB(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_background_tasks_tenant_status",
        "background_tasks",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_background_tasks_tenant_kind",
        "background_tasks",
        ["tenant_id", "kind"],
    )
    op.create_index(
        "uq_background_tasks_tenant_idempotency",
        "background_tasks",
        ["tenant_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_background_tasks_tenant_idempotency")
    op.drop_index("ix_background_tasks_tenant_kind")
    op.drop_index("ix_background_tasks_tenant_status")
    op.drop_table("background_tasks")
