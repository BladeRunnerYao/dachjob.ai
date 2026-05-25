"""Add user_id to candidate_profiles.

Each user gets their own private profile.

Revision ID: 0005_add_user_id_to_candidate_profiles
Revises: 0004_add_api_keys
Create Date: 2026-05-25
"""

from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import text

revision = "0005_add_user_id_to_candidate_profiles"
down_revision = "0004_add_api_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "candidate_profiles",
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index(op.f("ix_candidate_profiles_user_id"), "candidate_profiles", ["user_id"])

    conn = op.get_bind()

    profiles = conn.execute(
        text(
            "SELECT id, tenant_id, full_name, headline, location, timezone, raw_cv_md, profile_json, created_at, updated_at FROM candidate_profiles"
        )
    ).fetchall()

    for p in profiles:
        members = conn.execute(
            text("SELECT user_id FROM memberships WHERE tenant_id = :tid ORDER BY created_at"),
            {"tid": p.tenant_id},
        ).fetchall()

        for i, m in enumerate(members):
            uid = m.user_id
            existing = conn.execute(
                text("SELECT 1 FROM candidate_profiles WHERE user_id = :uid LIMIT 1"),
                {"uid": uid},
            ).fetchone()
            if existing:
                continue
            if i == 0:
                conn.execute(
                    text("UPDATE candidate_profiles SET user_id = :uid WHERE id = :pid"),
                    {"uid": uid, "pid": p.id},
                )
            else:
                new_id = uuid4()
                conn.execute(
                    text("""
                        INSERT INTO candidate_profiles (id, tenant_id, user_id, full_name, headline, location, timezone, raw_cv_md, profile_json, created_at, updated_at)
                        VALUES (:id, :tid, :uid, :fn, :hl, :loc, :tz, :md, :pj, :ca, :ua)
                    """),
                    {
                        "id": new_id,
                        "tid": p.tenant_id,
                        "uid": uid,
                        "fn": p.full_name,
                        "hl": p.headline,
                        "loc": p.location,
                        "tz": p.timezone,
                        "md": p.raw_cv_md,
                        "pj": p.profile_json,
                        "ca": p.created_at,
                        "ua": p.updated_at,
                    },
                )

    op.alter_column("candidate_profiles", "user_id", nullable=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_candidate_profiles_user_id"), table_name="candidate_profiles")
    op.drop_column("candidate_profiles", "user_id")
