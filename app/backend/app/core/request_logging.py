import logging
import time
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

request_id_var: ContextVar[str] = ContextVar("request_id", default="")
tenant_id_var: ContextVar[str] = ContextVar("tenant_id", default="")
user_id_var: ContextVar[str] = ContextVar("user_id", default="")

logger = logging.getLogger(__name__)


def get_request_id() -> str:
    return request_id_var.get()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request_id_var.set(request_id)

        start = time.monotonic()
        method = request.method
        path = request.url.path

        logger.info(
            "request_start | method=%s path=%s request_id=%s",
            method,
            path,
            request_id,
            extra={"request_id": request_id},
        )

        try:
            response: Response = await call_next(request)
            duration_ms = int((time.monotonic() - start) * 1000)
            response.headers["X-Request-ID"] = request_id

            logger.info(
                "request_end | method=%s path=%s status=%d duration_ms=%d request_id=%s",
                method,
                path,
                response.status_code,
                duration_ms,
                request_id,
                extra={"request_id": request_id, "status_code": response.status_code},
            )
            return response
        except Exception:
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.exception(
                "request_unhandled_error | method=%s path=%s duration_ms=%d request_id=%s",
                method,
                path,
                duration_ms,
                request_id,
                extra={"request_id": request_id},
            )
            raise
