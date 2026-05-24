from celery import Celery

from app.core.config import get_settings

settings = get_settings()
celery_app = Celery(
    "dachjob",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)
celery_app.conf.task_track_started = True
celery_app.conf.task_serializer = "json"
