import logging
import time
from collections import defaultdict
from collections.abc import Callable
from uuid import uuid4

from fastapi import Request, Response
from redis.asyncio import Redis
from redis.exceptions import RedisError
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.security import decode_access_token

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        max_requests: int = 60,
        authenticated_max_requests: int | None = None,
        window_seconds: int = 60,
        redis_url: str | None = None,
        exempt_routes: Callable[[str, str], bool] | None = None,
    ):
        super().__init__(app)
        self.max_requests = max_requests
        self.authenticated_max_requests = authenticated_max_requests or max_requests
        self.window_seconds = window_seconds
        self.redis_url = redis_url
        self.exempt_routes = exempt_routes
        self._windows: dict[str, list[float]] = defaultdict(list)
        self._redis: Redis | None = None
        self._redis_fallback_until = 0.0

    def _clean(self, key: str, now: float) -> None:
        cutoff = now - self.window_seconds
        window = self._windows[key]
        while window and window[0] <= cutoff:
            window.pop(0)

    def _client_key(self, request: Request) -> str:
        auth_header = request.headers.get("authorization", "")
        scheme, _, token = auth_header.partition(" ")
        if scheme.lower() == "bearer" and token:
            payload = decode_access_token(token.strip())
            subject = payload.get("sub") if payload else None
            if isinstance(subject, str) and subject:
                return f"user:{subject}"

        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            client_ip = forwarded_for.split(",", 1)[0].strip()
            if client_ip:
                return f"ip:{client_ip}"
        return f"ip:{request.client.host}" if request.client else "ip:unknown"

    def _max_requests_for_key(self, key: str) -> int:
        if key.startswith("user:"):
            return self.authenticated_max_requests
        return self.max_requests

    async def _get_redis(self) -> Redis | None:
        if not self.redis_url or time.time() < self._redis_fallback_until:
            return None
        if self._redis is None:
            self._redis = Redis.from_url(self.redis_url, encoding="utf-8", decode_responses=True)
        return self._redis

    async def _redis_retry_after(
        self, key: str, now: float, max_requests: int
    ) -> tuple[bool, int | None]:
        redis = await self._get_redis()
        if redis is None:
            return False, None

        now_ms = int(now * 1000)
        cutoff_ms = now_ms - (self.window_seconds * 1000)
        member = f"{now_ms}:{uuid4()}"
        redis_key = f"rate-limit:{key}"

        try:
            async with redis.pipeline(transaction=True) as pipe:
                pipe.zremrangebyscore(redis_key, 0, cutoff_ms)
                pipe.zadd(redis_key, {member: now_ms})
                pipe.zcard(redis_key)
                pipe.expire(redis_key, self.window_seconds * 2)
                results = await pipe.execute()
        except RedisError:
            logger.warning("Redis rate limiter unavailable; falling back to in-memory window")
            self._redis_fallback_until = now + 30
            return False, None

        count = int(results[2])
        if count <= max_requests:
            return True, None
        return True, self.window_seconds

    def _memory_retry_after(self, key: str, now: float, max_requests: int) -> int | None:
        self._clean(key, now)
        self._windows[key].append(now)
        if len(self._windows[key]) <= max_requests:
            return None
        return self.window_seconds

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method
        if self.exempt_routes and self.exempt_routes(path, method):
            return await call_next(request)

        key = self._client_key(request)
        max_requests = self._max_requests_for_key(key)
        now = time.time()
        used_redis, retry_after = await self._redis_retry_after(key, now, max_requests)
        if not used_redis:
            retry_after = self._memory_retry_after(key, now, max_requests)
        if retry_after is not None:
            logger.warning(
                "rate_limit_exceeded | method=%s path=%s key_type=%s retry_after=%d",
                method,
                path,
                key.split(":", 1)[0],
                retry_after,
            )
            return Response(
                content='{"error":{"code":"rate_limit_exceeded","message":"Too many requests"}}',
                status_code=429,
                headers={
                    "Retry-After": str(retry_after),
                    "Content-Type": "application/json",
                },
            )
        return await call_next(request)
