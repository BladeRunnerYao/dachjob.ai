import asyncio
import json
import logging
import os

from celery import Celery
from celery.signals import worker_ready, task_prerun, task_postrun, task_failure

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import async_session_factory

configure_logging()
logger = logging.getLogger(__name__)

settings = get_settings()
celery_app = Celery(
    "dachjob",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)
celery_app.conf.task_track_started = True
celery_app.conf.task_serializer = "json"

celery_app.conf.task_routes = {
    "app.workers.tasks.import_jobs_task": {"queue": "jobs"},
    "app.workers.tasks.parse_job_task": {"queue": "jobs"},
    "app.workers.tasks.compute_match_task": {"queue": "jobs"},
    "app.workers.tasks.generate_resume_task": {"queue": "llm"},
    "app.workers.tasks.send_email_task": {"queue": "email"},
}

celery_app.conf.worker_prefetch_multiplier = 1
celery_app.conf.task_acks_late = True
celery_app.conf.task_reject_on_worker_lost = True
celery_app.conf.task_time_limit = 15 * 60
celery_app.conf.task_soft_time_limit = 12 * 60
celery_app.conf.result_expires = 24 * 3600


def run_async(coro):
    return asyncio.run(coro)


@worker_ready.connect
def on_worker_ready(**kwargs):
    path = os.path.join(os.path.dirname(__file__), "..", "..", "version.json")
    try:
        with open(path) as f:
            v = json.load(f)
    except Exception:
        v = {"branch": "unknown", "commit": "unknown"}
    logger.info(
        "Celery worker ready | branch=%s commit=%s provider=%s",
        v.get("branch"), v.get("commit"), settings.llm_provider,
    )


@task_prerun.connect
def on_task_prerun(task_id, task, **kwargs):
    logger.info(
        "task_started | celery_task_id=%s task_name=%s",
        task_id, task.name,
    )


@task_postrun.connect
def on_task_postrun(task_id, task, state, retval, **kwargs):
    logger.info(
        "task_finished | celery_task_id=%s task_name=%s state=%s",
        task_id, task.name, state,
    )


@task_failure.connect
def on_task_failure(task_id, exception, traceback, **kwargs):
    logger.error(
        "task_failed | celery_task_id=%s error=%s",
        task_id, str(exception)[:200],
    )
