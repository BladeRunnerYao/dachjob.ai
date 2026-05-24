from uuid import uuid4

import pytest
from fastapi.routing import APIRoute

from app.core.auth import is_public_route
from app.core.errors import AppError, app_error_handler
from app.main import app


def test_public_route_whitelist_is_exact():
    artifact_id = uuid4()

    assert is_public_route("/api/health", "GET")
    assert is_public_route("/api/version", "GET")
    assert is_public_route("/api/auth/login", "POST")
    assert is_public_route("/api/auth/forgot-password", "POST")
    assert is_public_route("/api/auth/reset-password", "POST")
    assert is_public_route(f"/api/resumes/{artifact_id}/html", "GET")

    assert not is_public_route("/api/jobs", "GET")
    assert not is_public_route("/api/auth/login", "GET")
    assert not is_public_route(f"/api/resumes/{artifact_id}/html", "POST")
    assert not is_public_route(f"/api/resumes/{artifact_id}", "GET")
    assert not is_public_route("/api/resumes/not-a-uuid/html", "GET")


@pytest.mark.asyncio
async def test_app_error_handler_preserves_status_code():
    response = await app_error_handler(
        None,
        AppError("authentication_required", "Authentication required", status_code=401),
    )

    assert response.status_code == 401


def test_all_business_routes_have_auth_dependency():
    public_routes = {
        ("GET", "/api/health"),
        ("GET", "/api/version"),
        ("POST", "/api/auth/register"),
        ("POST", "/api/auth/login"),
        ("POST", "/api/auth/forgot-password"),
        ("POST", "/api/auth/reset-password"),
        ("POST", "/api/auth/google"),
        ("GET", "/api/resumes/{artifact_id}/html"),
    }
    auth_dependencies = {"get_tenant_context", "get_current_user"}

    missing_auth = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        methods = route.methods - {"HEAD", "OPTIONS"}
        for method in methods:
            if (method, route.path_format) in public_routes:
                continue
            dependency_names = {
                dependency.call.__name__
                for dependency in route.dependant.dependencies
                if dependency.call is not None
            }
            if not dependency_names.intersection(auth_dependencies):
                missing_auth.append(f"{method} {route.path_format}")

    assert missing_auth == []
