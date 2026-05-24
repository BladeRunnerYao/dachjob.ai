import json
import logging
import os

from celery import Celery
from celery.signals import worker_ready

from app.core.config import get_settings

logger = logging.getLogger("celery")

settings = get_settings()
celery_app = Celery("dachjob", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.task_track_started = True
celery_app.conf.task_serializer = "json"


@worker_ready.connect
def on_worker_ready(**kwargs):
    path = os.path.join(os.path.dirname(__file__), "..", "version.json")
    try:
        with open(path) as f:
            v = json.load(f)
    except Exception:
        v = {"branch": "unknown", "commit": "unknown"}
    logger.info(
        "Celery worker ready | branch=%s commit=%s provider=%s",
        v.get("branch"), v.get("commit"), settings.llm_provider,
    )
