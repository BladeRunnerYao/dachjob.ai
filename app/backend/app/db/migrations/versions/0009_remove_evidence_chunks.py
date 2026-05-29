"""Remove evidence_chunks table and related indexes.

Remove the evidence_chunks table and its performance index,
as evidence mapping/chunking has been removed from the application.

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-28
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_evidence_chunks_profile_id")
    op.drop_index(op.f("ix_evidence_chunks_tenant_id"), table_name="evidence_chunks")
    op.drop_table("evidence_chunks")


def downgrade() -> None:
    op.create_table(
        "evidence_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False
        ),
        sa.Column(
            "profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("candidate_profiles.id"),
            nullable=False,
        ),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("source_label", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("embedding", sa.ARRAY(sa.Float()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(op.f("ix_evidence_chunks_tenant_id"), "evidence_chunks", ["tenant_id"])
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_evidence_chunks_profile_id ON evidence_chunks (profile_id)"
    )
