from types import SimpleNamespace
from uuid import uuid4

from app.core.rate_limit import RateLimitMiddleware
from app.core.security import create_access_token


async def _empty_app(scope, receive, send):
    return None


def test_rate_limit_key_prefers_authenticated_user():
    user_id = uuid4()
    token = create_access_token(user_id, "user@example.com")
    request = SimpleNamespace(
        headers={
            "authorization": f"Bearer {token}",
            "x-forwarded-for": "203.0.113.10, 169.254.169.126",
        },
        client=SimpleNamespace(host="169.254.169.126"),
    )
    middleware = RateLimitMiddleware(_empty_app)

    assert middleware._client_key(request) == f"user:{user_id}"


def test_rate_limit_key_uses_forwarded_ip_without_token():
    request = SimpleNamespace(
        headers={"x-forwarded-for": "203.0.113.10, 169.254.169.126"},
        client=SimpleNamespace(host="169.254.169.126"),
    )
    middleware = RateLimitMiddleware(_empty_app)

    assert middleware._client_key(request) == "ip:203.0.113.10"


def test_rate_limit_uses_higher_authenticated_limit():
    middleware = RateLimitMiddleware(_empty_app, max_requests=60, authenticated_max_requests=180)

    assert middleware._max_requests_for_key("ip:203.0.113.10") == 60
    assert middleware._max_requests_for_key(f"user:{uuid4()}") == 180
