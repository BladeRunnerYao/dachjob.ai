"""Add job import metadata and skills.

Revision ID: 0002_job_import_metadata
Revises: 0001_initial_schema
Create Date: 2026-05-23
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0002_job_import_metadata"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("job_postings", sa.Column("source", sa.Text(), nullable=True))
    op.add_column("job_postings", sa.Column("source_job_id", sa.Text(), nullable=True))
    op.add_column("job_postings", sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("job_postings", sa.Column("employment_type", sa.Text(), nullable=True))
    op.add_column("job_postings", sa.Column("workplace", sa.Text(), nullable=True))
    op.add_column("job_postings", sa.Column("salary_text", sa.Text(), nullable=True))
    op.add_column(
        "job_postings",
        sa.Column("scraped_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    op.create_table(
        "job_skills",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("job_postings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Numeric(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("job_id", "name", "category", name="uq_job_skills_job_name_category"),
    )
    op.create_index(op.f("ix_job_skills_tenant_id"), "job_skills", ["tenant_id"])
    op.create_index(op.f("ix_job_skills_job_id"), "job_skills", ["job_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_job_skills_job_id"), table_name="job_skills")
    op.drop_index(op.f("ix_job_skills_tenant_id"), table_name="job_skills")
    op.drop_table("job_skills")

    op.drop_column("job_postings", "scraped_json")
    op.drop_column("job_postings", "salary_text")
    op.drop_column("job_postings", "workplace")
    op.drop_column("job_postings", "employment_type")
    op.drop_column("job_postings", "posted_at")
    op.drop_column("job_postings", "source_job_id")
    op.drop_column("job_postings", "source")
