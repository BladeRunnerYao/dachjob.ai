import uuid

from sqlalchemy.dialects import postgresql

from app.core.auth import TenantContext
from app.modules.resumes.routes import _artifact_owner_filters
from app.modules.resumes.service import _profile_query_for_resume


def _compiled_sql(query) -> str:
    return str(query.compile(dialect=postgresql.dialect()))


def _where_clause(sql: str) -> str:
    return sql.split("WHERE", 1)[1]


def test_resume_profile_query_scopes_to_authenticated_user():
    tenant = TenantContext(
        id=uuid.uuid4(),
        slug="dachjob",
        name="dachjob",
        user_id=uuid.uuid4(),
    )

    sql = _compiled_sql(_profile_query_for_resume(tenant))

    where = _where_clause(sql)

    assert "candidate_profiles.tenant_id" in where
    assert "candidate_profiles.user_id" in where


def test_resume_profile_query_keeps_api_key_tenant_fallback():
    tenant = TenantContext(
        id=uuid.uuid4(),
        slug="dachjob",
        name="dachjob",
        user_id=None,
    )

    sql = _compiled_sql(_profile_query_for_resume(tenant))

    where = _where_clause(sql)

    assert "candidate_profiles.tenant_id" in where
    assert "candidate_profiles.user_id" not in where


def test_resume_artifact_filters_scope_to_authenticated_user():
    tenant = TenantContext(
        id=uuid.uuid4(),
        slug="dachjob",
        name="dachjob",
        user_id=uuid.uuid4(),
    )

    filters = [str(f) for f in _artifact_owner_filters(tenant)]

    assert any("resume_artifacts.tenant_id" in f for f in filters)
    assert any("resume_artifacts.user_id" in f for f in filters)


def test_resume_artifact_filters_keep_api_key_tenant_fallback():
    tenant = TenantContext(
        id=uuid.uuid4(),
        slug="dachjob",
        name="dachjob",
        user_id=None,
    )

    filters = [str(f) for f in _artifact_owner_filters(tenant)]

    assert any("resume_artifacts.tenant_id" in f for f in filters)
    assert not any("resume_artifacts.user_id" in f for f in filters)
