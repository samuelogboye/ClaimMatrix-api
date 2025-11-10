"""Celery application configuration."""
from celery import Celery
from celery.schedules import crontab

from app.config import settings

# Create Celery app
celery_app = Celery(
    "claimmatrix",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.claim_tasks"],
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,  # Hard timeout from config
    task_soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT,  # Soft timeout from config
    worker_prefetch_multiplier=4,  # How many tasks worker prefetches
    worker_max_tasks_per_child=1000,  # Restart worker after N tasks (prevents memory leaks)
    task_acks_late=True,  # Acknowledge task after execution (safer)
    task_reject_on_worker_lost=True,  # Reject task if worker crashes
    result_expires=3600,  # Task results expire after 1 hour
)

# Celery Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    "run-ml-audit": {
        "task": "app.tasks.claim_tasks.run_ml_audit",
        "schedule": crontab(hour="*/6"),  # Run every 6 hours
    },
}

if __name__ == "__main__":
    celery_app.start()
