"""Add user_id to candidate_profiles.

Each user gets their own private profile.

Revision ID: 0005_add_user_id_to_candidate_profiles
Revises: 0004_add_api_keys
Create Date: 2026-05-25
"""

from uuid import uuid4

from alembic import op
from sqlalchemy.sql import text

revision = "0005"
down_revision = "0004_add_api_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE candidate_profiles ADD COLUMN IF NOT EXISTS "
        "user_id UUID REFERENCES users(id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_candidate_profiles_user_id "
        "ON candidate_profiles (user_id)"
    )

    conn = op.get_bind()

    unassigned = conn.execute(
        text("SELECT id, tenant_id FROM candidate_profiles WHERE user_id IS NULL LIMIT 1")
    ).fetchall()

    if not unassigned:
        op.execute("ALTER TABLE candidate_profiles ALTER COLUMN user_id SET NOT NULL")
        return

    for p in unassigned:
        members = conn.execute(
            text("SELECT user_id FROM memberships WHERE tenant_id = :tid"),
            {"tid": p.tenant_id},
        ).fetchall()

        profile_row = conn.execute(
            text(
                "SELECT id, full_name, headline, location, timezone, "
                "raw_cv_md, created_at, updated_at "
                "FROM candidate_profiles WHERE id = :pid"
            ),
            {"pid": p.id},
        ).fetchone()

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
                        INSERT INTO candidate_profiles
                          (id, tenant_id, user_id, full_name, headline,
                           location, timezone, raw_cv_md,
                           created_at, updated_at)
                        VALUES (:id, :tid, :uid, :fn, :hl,
                                :loc, :tz, :md,
                                :ca, :ua)
                    """),
                    {
                        "id": new_id, "tid": p.tenant_id, "uid": uid,
                        "fn": profile_row.full_name, "hl": profile_row.headline,
                        "loc": profile_row.location, "tz": profile_row.timezone,
                        "md": profile_row.raw_cv_md,
                        "ca": profile_row.created_at, "ua": profile_row.updated_at,
                    },
                )

    op.execute("ALTER TABLE candidate_profiles ALTER COLUMN user_id SET NOT NULL")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_candidate_profiles_user_id")
    op.execute("ALTER TABLE candidate_profiles DROP COLUMN IF EXISTS user_id")
