"""
Celery Application Configuration

Creates and configures the Celery application instance.

Workers are started with:
    celery -A app.tasks.celery_app worker --loglevel=info

Beat scheduler (periodic tasks):
    celery -A app.tasks.celery_app beat --loglevel=info
"""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab
from kombu import Exchange, Queue

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Celery application instance
# ---------------------------------------------------------------------------

celery_app = Celery(
    "kyc_tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.kyc_tasks"],
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Task execution
    task_soft_time_limit=settings.CELERY_TASK_TIMEOUT,
    task_time_limit=settings.CELERY_TASK_TIMEOUT + 30,
    task_acks_late=True,         # Acknowledge after task completes (safer)
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,  # One task per worker at a time (fair dispatch)

    # Results
    result_expires=86400,       # Store results for 24 hours
    result_persistent=True,

    # Retry behaviour defaults
    task_max_retries=3,
    task_default_retry_delay=60,  # Seconds between retries

    # Routing
    task_default_queue="default",
    task_queues=(
        Queue("default", Exchange("default"), routing_key="default"),
        Queue("kyc_processing", Exchange("kyc"), routing_key="kyc.#"),
        Queue("notifications", Exchange("notifications"), routing_key="notify.#"),
    ),
    task_routes={
        "app.tasks.kyc_tasks.process_kyc_submission": {
            "queue": "kyc_processing",
            "routing_key": "kyc.process",
        },
        "app.tasks.kyc_tasks.send_status_notification": {
            "queue": "notifications",
            "routing_key": "notify.kyc",
        },
        "app.tasks.kyc_tasks.cleanup_expired_submissions": {
            "queue": "default",
        },
    },

    # Beat schedule (periodic tasks)
    beat_schedule={
        "cleanup-expired-submissions": {
            "task": "app.tasks.kyc_tasks.cleanup_expired_submissions",
            "schedule": crontab(hour=2, minute=0),  # Daily at 02:00 UTC
            "options": {"queue": "default"},
        },
    },

    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
)

logger.info(
    "Celery application configured",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)
