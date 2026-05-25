import json
import logging
import os
import traceback
from datetime import datetime, timezone
from typing import Any

from app.core.config import get_settings


class ErrorArchiveHandler(logging.Handler):
    def __init__(self, error_log_dir: str) -> None:
        super().__init__(logging.ERROR)
        self.error_log_dir = error_log_dir
        self.setLevel(logging.ERROR)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            log_dir = os.path.join(self.error_log_dir, date_str)
            os.makedirs(log_dir, exist_ok=True)
            log_path = os.path.join(log_dir, "errors.jsonl")

            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "exception_type": None,
                "exception_message": None,
                "traceback": None,
            }

            if record.exc_info:
                exc_type, exc_value, exc_tb = record.exc_info
                if exc_type and exc_value:
                    entry["exception_type"] = exc_type.__name__
                    entry["exception_message"] = str(exc_value)[:500]
                    entry["traceback"] = "".join(
                        traceback.format_exception(exc_type, exc_value, exc_tb)
                    )[:2000]

            for key in (
                "request_id",
                "tenant_id",
                "user_id",
                "background_task_id",
                "celery_task_id",
                "operation",
                "job_id",
                "task_id",
            ):
                value = getattr(record, key, None)
                if value is not None:
                    entry[key] = str(value)

            with open(log_path, "a") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except Exception:
            import sys

            print(
                f"ErrorArchiveHandler: failed to write error log: {sys.exc_info()[1]}",
                file=sys.stderr,
            )


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in (
            "request_id",
            "tenant_id",
            "user_id",
            "background_task_id",
            "celery_task_id",
            "operation",
            "job_id",
            "task_id",
        ):
            value = getattr(record, key, None)
            if value is not None:
                entry[key] = str(value)
        if record.exc_info:
            exc_type, exc_value, _ = record.exc_info
            if exc_type and exc_value:
                entry["exception"] = f"{exc_type.__name__}: {str(exc_value)[:200]}"
        return json.dumps(entry, default=str)


def configure_logging() -> None:
    settings = get_settings()

    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level)
    if settings.log_json:
        stream_handler.setFormatter(JsonFormatter())
    else:
        stream_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
    root_logger.addHandler(stream_handler)

    if settings.error_log_to_file:
        error_handler = ErrorArchiveHandler(settings.error_log_dir)
        root_logger.addHandler(error_handler)

    logging.getLogger("uvicorn").setLevel(level)
    logging.getLogger("celery").setLevel(level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def record_error_log(
    message: str,
    *,
    exc: BaseException | None = None,
    **context: Any,
) -> None:
    logger = logging.getLogger("app.errors")
    extra = {k: v for k, v in context.items() if v is not None}
    if exc:
        logger.error(message, exc_info=exc, extra=extra)
    else:
        logger.error(message, extra=extra)
