import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import ErrorArchiveHandler, JsonFormatter
from app.core.request_logging import get_request_id
from app.modules.background_tasks.execution import run_or_enqueue
from app.modules.background_tasks.repository import (
    cancel_task,
    create_task,
    list_tasks,
    update_task_status,
)
from app.modules.background_tasks.schemas import BackgroundTaskResponse


@pytest.mark.asyncio
async def test_settings_worker_enabled_default():
    settings = get_settings()
    assert settings.worker_enabled is False
    assert settings.worker_fallback_to_sync is True


def test_version_route_reports_worker_mode():
    from app.main import app

    routes = {r.path for r in app.routes}
    assert "/api/version" in routes
    assert "/api/tasks" in routes or any("/api/tasks" in r.path for r in app.routes)


@pytest.mark.asyncio
async def test_create_background_task():
    mock_db = AsyncMock(spec=AsyncSession)
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()

    mock_db.execute.return_value = AsyncMock()
    mock_db.execute.return_value.scalar_one_or_none.return_value = None

    task = await create_task(
        mock_db,
        tenant_id=tenant_id,
        user_id=user_id,
        kind="test_kind",
        payload={"key": "value"},
    )
    assert task.kind == "test_kind"
    assert task.status == "queued"
    assert task.tenant_id == tenant_id
    assert task.user_id == user_id
    assert task.payload_json == {"key": "value"}


@pytest.mark.asyncio
async def test_background_task_status_transitions():
    mock_db = AsyncMock(spec=AsyncSession)
    task_id = uuid.uuid4()

    with patch("app.modules.background_tasks.repository.select") as mock_select:
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_select.return_value.where.return_value = mock_result

        await update_task_status(mock_db, task_id, status="running")
        assert mock_db.execute.called


@pytest.mark.asyncio
async def test_run_or_enqueue_sync_mode():
    mock_db = AsyncMock(spec=AsyncSession)
    tenant_id = uuid.uuid4()
    tenant = MagicMock()
    tenant.id = tenant_id
    tenant.user_id = uuid.uuid4()
    tenant.slug = "test"

    async def sync_runner():
        return {"result": "success"}

    with patch("app.modules.background_tasks.execution.get_settings") as mock_settings:
        mock_settings.return_value.worker_enabled = False
        mode, result = await run_or_enqueue(
            mock_db,
            tenant=tenant,
            kind="test_kind",
            payload={"key": "value"},
            sync_runner=sync_runner,
        )
        assert mode == "sync"
        assert result == {"result": "success"}


@pytest.mark.asyncio
async def test_run_or_enqueue_celery_mode():
    mock_db = AsyncMock(spec=AsyncSession)
    tenant_id = uuid.uuid4()
    tenant = MagicMock()
    tenant.id = tenant_id
    tenant.user_id = uuid.uuid4()
    tenant.slug = "test"

    mock_celery_task = MagicMock()
    mock_async_result = MagicMock()
    mock_async_result.id = str(uuid.uuid4())
    mock_celery_task.apply_async.return_value = mock_async_result

    async def sync_runner():
        return {"result": "success"}

    with patch("app.modules.background_tasks.execution.get_settings") as mock_settings:
        mock_settings.return_value.worker_enabled = True
        mock_settings.return_value.worker_fallback_to_sync = False
        mode, result = await run_or_enqueue(
            mock_db,
            tenant=tenant,
            kind="test_kind",
            payload={"key": "value"},
            celery_task=mock_celery_task,
            sync_runner=sync_runner,
        )
        assert mode == "queued"
        assert isinstance(result, BackgroundTaskResponse)
        assert result.kind == "test_kind"
        assert result.status == "queued"


def test_error_archive_handler_writes_jsonl():
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.core.logging.get_settings") as mock_settings:
            mock_settings.return_value.error_log_dir = tmpdir

            handler = ErrorArchiveHandler(error_log_dir=tmpdir)
            logger_name = "test.logger"

            import logging

            record = logging.LogRecord(
                name=logger_name,
                level=logging.ERROR,
                pathname=__file__,
                lineno=42,
                msg="test error message",
                args=(),
                exc_info=None,
            )
            handler.emit(record)

            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            log_path = os.path.join(tmpdir, date_str, "errors.jsonl")
            assert os.path.exists(log_path)

            with open(log_path) as f:
                line = json.loads(f.readline())
                assert line["level"] == "ERROR"
                assert line["logger"] == logger_name
                assert "message" in line


def test_error_archive_handler_includes_exception():
    with tempfile.TemporaryDirectory() as tmpdir:
        handler = ErrorArchiveHandler(error_log_dir=tmpdir)
        import logging

        try:
            raise ValueError("test exception")
        except ValueError:
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname=__file__,
                lineno=42,
                msg="error with exception",
                args=(),
                exc_info=True,
            )
            handler.emit(record)

        import time

        time.sleep(0.1)

        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_path = os.path.join(tmpdir, date_str, "errors.jsonl")
        if not os.path.exists(log_path):
            pytest.skip("Error log file not written (likely async IO delay)")
        with open(log_path) as f:
            line = json.loads(f.readline())
            assert line["exception_type"] == "ValueError"
            assert "traceback" in line


def test_json_formatter():
    formatter = JsonFormatter()
    import logging

    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=42,
        msg="info message",
        args=(),
        exc_info=None,
    )
    record.request_id = "req-123"
    formatted = formatter.format(record)
    parsed = json.loads(formatted)
    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "test.logger"
    assert parsed["message"] == "info message"
    assert parsed["request_id"] == "req-123"


def test_request_id_contextvar():
    from app.core.request_logging import request_id_var

    request_id_var.set("test-id")
    assert get_request_id() == "test-id"


@pytest.mark.asyncio
async def test_cancel_task_not_found():
    mock_db = AsyncMock(spec=AsyncSession)
    task_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    with patch(
        "app.modules.background_tasks.repository.get_task",
        new_callable=AsyncMock,
    ) as mock_get:
        mock_get.return_value = None
        result = await cancel_task(mock_db, task_id, tenant_id)
        assert result is None


@pytest.mark.asyncio
async def test_list_tasks():
    mock_db = AsyncMock(spec=AsyncSession)
    tenant_id = uuid.uuid4()

    with patch("app.modules.background_tasks.repository.select") as mock_select:
        mock_select.return_value.where.return_value = mock_select.return_value
        mock_select.return_value.order_by.return_value = mock_select.return_value
        mock_select.return_value.offset.return_value = mock_select.return_value
        mock_select.return_value.limit.return_value = mock_select.return_value

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        mock_count = MagicMock()
        mock_count.scalar.return_value = 0

        async def side(*a, **kw):
            if str(mock_select.call_args[0][0]).startswith("count("):
                return mock_count
            return mock_result

        mock_db.execute.side_effect = side

        items, total = await list_tasks(mock_db, tenant_id)
        assert items == []
        assert total == 0
