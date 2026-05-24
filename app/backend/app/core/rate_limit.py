import time
from collections import defaultdict
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        max_requests: int = 60,
        window_seconds: int = 60,
        exempt_paths: Callable[[str], bool] | None = None,
    ):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.exempt_paths = exempt_paths
        self._windows: dict[str, list[float]] = defaultdict(list)

    def _clean(self, key: str, now: float) -> None:
        cutoff = now - self.window_seconds
        window = self._windows[key]
        while window and window[0] <= cutoff:
            window.pop(0)

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if self.exempt_paths and self.exempt_paths(path):
            return await call_next(request)
        client_ip = request.client.host if request.client else "unknown"
        key = f"{client_ip}:{path}"
        now = time.time()
        self._clean(key, now)
        self._windows[key].append(now)
        if len(self._windows[key]) > self.max_requests:
            return Response(
                content='{"error":{"code":"rate_limit_exceeded","message":"Too many requests"}}',
                status_code=429,
                headers={
                    "Retry-After": str(self.window_seconds),
                    "Content-Type": "application/json",
                },
            )
        return await call_next(request)
