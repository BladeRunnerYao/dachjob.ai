"""Add multi-country job filter metadata.

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-05
"""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "job_postings",
        sa.Column("countries", sa.Text(), server_default="", nullable=False),
    )
    op.execute(
        """
        UPDATE job_postings
        SET countries =
          CASE
            WHEN lower(location) LIKE '%germany%'
              OR lower(location) LIKE '%deutschland%'
              OR lower(location) LIKE '%berlin%'
              OR lower(location) LIKE '%hamburg%'
              OR lower(location) LIKE '%munich%'
              OR lower(location) LIKE '%münchen%'
              OR lower(location) LIKE '%frankfurt%'
              OR lower(location) LIKE '%stuttgart%'
              OR lower(location) LIKE '%leipzig%'
            THEN '|Germany|' ELSE '' END ||
          CASE
            WHEN lower(location) LIKE '%switzerland%'
              OR lower(location) LIKE '%schweiz%'
              OR lower(location) LIKE '%zurich%'
              OR lower(location) LIKE '%zürich%'
              OR lower(location) LIKE '%basel%'
              OR lower(location) LIKE '%bern%'
              OR lower(location) LIKE '%geneva%'
              OR lower(location) LIKE '%lausanne%'
              OR lower(location) LIKE '%zug%'
            THEN '|Switzerland|' ELSE '' END ||
          CASE
            WHEN lower(location) LIKE '%austria%'
              OR lower(location) LIKE '%österreich%'
              OR lower(location) LIKE '%vienna%'
              OR lower(location) LIKE '%wien%'
            THEN '|Austria|' ELSE '' END ||
          CASE
            WHEN lower(location) LIKE '%united states%'
              OR lower(location) LIKE '%usa%'
              OR lower(location) LIKE '%san francisco%'
              OR lower(location) LIKE '%new york%'
              OR lower(location) LIKE '%seattle%'
              OR lower(location) LIKE '%austin%'
              OR lower(location) LIKE '%, ca%'
              OR lower(location) LIKE '%, ny%'
              OR lower(location) LIKE '%, tx%'
              OR lower(location) LIKE '%, wa%'
              OR lower(location) LIKE '%, ma%'
            THEN '|United States|' ELSE '' END ||
          CASE
            WHEN lower(location) LIKE '%spain%'
              OR lower(location) LIKE '%barcelona%'
              OR lower(location) LIKE '%madrid%'
            THEN '|Spain|' ELSE '' END ||
          CASE
            WHEN lower(location) LIKE '%united kingdom%'
              OR lower(location) LIKE '%london%'
              OR lower(location) LIKE '%/uk%'
            THEN '|United Kingdom|' ELSE '' END ||
          CASE WHEN lower(location) LIKE '%ireland%' OR lower(location) LIKE '%dublin%' THEN '|Ireland|' ELSE '' END ||
          CASE WHEN lower(location) LIKE '%romania%' OR lower(location) LIKE '%iasi%' THEN '|Romania|' ELSE '' END ||
          CASE WHEN lower(location) LIKE '%italy%' THEN '|Italy|' ELSE '' END ||
          CASE WHEN lower(location) LIKE '%portugal%' THEN '|Portugal|' ELSE '' END ||
          CASE WHEN lower(location) LIKE '%netherlands%' OR lower(location) LIKE '%amsterdam%' THEN '|Netherlands|' ELSE '' END ||
          CASE WHEN lower(location) LIKE '%france%' OR lower(location) LIKE '%paris%' THEN '|France|' ELSE '' END ||
          CASE WHEN lower(location) LIKE '%thailand%' OR lower(location) LIKE '%bangkok%' THEN '|Thailand|' ELSE '' END ||
          CASE WHEN lower(location) LIKE '%japan%' OR lower(location) LIKE '%tokyo%' OR lower(location) LIKE '%yokohama%' THEN '|Japan|' ELSE '' END ||
          CASE WHEN lower(location) LIKE '%hungary%' OR lower(location) LIKE '%budapest%' THEN '|Hungary|' ELSE '' END ||
          CASE WHEN lower(location) LIKE '%greece%' OR lower(location) LIKE '%athens%' THEN '|Greece|' ELSE '' END
        WHERE COALESCE(TRIM(location), '') != ''
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_job_postings_tenant_countries "
        "ON job_postings (tenant_id, countries)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_job_postings_tenant_countries")
    op.drop_column("job_postings", "countries")
