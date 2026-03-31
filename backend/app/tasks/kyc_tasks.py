"""
KYC Celery Tasks

Defines the async Celery tasks that drive KYC processing:

  process_kyc_submission       – Main task: builds initial state, runs LangGraph
  cleanup_expired_submissions  – Periodic task: marks old submissions as EXPIRED
  send_status_notification     – Notification task: emails / webhooks on status change
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from celery import Task
from celery.exceptions import MaxRetriesExceededError
from celery.utils.log import get_task_logger

from app.tasks.celery_app import celery_app

logger = get_task_logger(__name__)


# ---------------------------------------------------------------------------
# Base task class with error reporting
# ---------------------------------------------------------------------------


class BaseKYCTask(Task):
    """Base class that updates the submission status on unexpected failure."""

    abstract = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called when a task raises an unhandled exception."""
        submission_id = kwargs.get("submission_id") or (args[0] if args else "unknown")
        logger.error(
            "Celery task failed",
            task_id=task_id,
            submission_id=submission_id,
            error=str(exc),
            exc_info=True,
        )
        _mark_submission_error(submission_id, str(exc))


# ---------------------------------------------------------------------------
# Main processing task
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    base=BaseKYCTask,
    name="app.tasks.kyc_tasks.process_kyc_submission",
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
    queue="kyc_processing",
)
def process_kyc_submission(
    self,
    submission_id: str,
    user_id: str,
    form_data: Dict[str, Any],
    document_ids: List[str],
) -> Dict[str, Any]:
    """
    Celery task: run the full KYC LangGraph pipeline for one submission.

    Steps:
      1. Build the initial KYCAgentState
      2. Invoke the compiled LangGraph graph synchronously
      3. Store the final state back on the KYCSubmission record

    Args:
        submission_id: KYC submission UUID string.
        user_id:       User UUID string.
        form_data:     Applicant form fields.
        document_ids:  List of document UUID strings.

    Returns:
        Dict summary of the final agent state.
    """
    from datetime import datetime, timezone  # noqa: PLC0415
    from app.graph.kyc_graph import get_kyc_graph  # noqa: PLC0415

    logger.info(
        "Starting KYC processing task",
        submission_id=submission_id,
        task_id=self.request.id,
    )

    started_at = datetime.now(timezone.utc).isoformat()

    initial_state: Dict[str, Any] = {
        "kyc_submission_id": submission_id,
        "user_id": user_id,
        "form_data": form_data,
        "document_ids": document_ids,
        "current_agent": "",
        "retry_count": 0,
        "errors": [],
        "ocr_results": [],
        "extracted_name": None,
        "extracted_dob": None,
        "extracted_id_number": None,
        "extracted_address": None,
        "name_match_score": None,
        "dob_match": None,
        "id_match": None,
        "fraud_flags": [],
        "duplicate_detected": None,
        "confidence_score": None,
        "risk_level": None,
        "decision": None,
        "decision_reason": None,
        "started_at": started_at,
        "completed_at": None,
        "processing_time_ms": None,
    }

    try:
        graph = get_kyc_graph()
        final_state = graph.invoke(initial_state)

        logger.info(
            "KYC processing completed",
            submission_id=submission_id,
            decision=final_state.get("decision"),
            confidence=final_state.get("confidence_score"),
        )

        # Send status notification (fire and forget)
        send_status_notification.delay(
            submission_id=submission_id,
            user_id=user_id,
            new_status=final_state.get("decision", "MANUAL_REVIEW"),
            reason=final_state.get("decision_reason", ""),
        )

        return {
            "submission_id": submission_id,
            "decision": final_state.get("decision"),
            "confidence_score": final_state.get("confidence_score"),
            "risk_level": final_state.get("risk_level"),
            "processing_time_ms": final_state.get("processing_time_ms"),
        }

    except Exception as exc:
        logger.error(
            "KYC processing task error",
            submission_id=submission_id,
            error=str(exc),
            exc_info=True,
        )
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.error(
                "Max retries exceeded for KYC task",
                submission_id=submission_id,
            )
            _mark_submission_error(submission_id, str(exc))
            raise


# ---------------------------------------------------------------------------
# Cleanup expired submissions
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    name="app.tasks.kyc_tasks.cleanup_expired_submissions",
    queue="default",
)
def cleanup_expired_submissions(self) -> Dict[str, Any]:
    """
    Periodic task: mark KYC submissions that have exceeded the expiry window
    as EXPIRED.

    Submissions in SUBMITTED or PROCESSING state older than 7 days are
    considered stale and automatically expired.
    """
    logger.info("Running expired submissions cleanup")

    cutoff = datetime.now(timezone.utc) - timedelta(days=7)

    expired_count = 0
    error_count = 0

    async def _cleanup():
        nonlocal expired_count, error_count

        from sqlalchemy import select, and_  # noqa: PLC0415
        from app.core.database import AsyncSessionLocal  # noqa: PLC0415
        from app.models.kyc import KYCSubmission, KYCStatus  # noqa: PLC0415

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(KYCSubmission).where(
                    and_(
                        KYCSubmission.status.in_(
                            [KYCStatus.SUBMITTED, KYCStatus.PROCESSING]
                        ),
                        KYCSubmission.created_at < cutoff,
                    )
                )
            )
            stale_submissions = result.scalars().all()

            for submission in stale_submissions:
                try:
                    submission.status = KYCStatus.EXPIRED
                    submission.status_reason = (
                        "Automatically expired: processing not completed within 7 days."
                    )
                    expired_count += 1
                except Exception as exc:
                    logger.error(
                        "Error expiring submission",
                        submission_id=str(submission.id),
                        error=str(exc),
                    )
                    error_count += 1

            await session.commit()

    asyncio.run(_cleanup())

    logger.info(
        "Expired submissions cleanup completed",
        expired=expired_count,
        errors=error_count,
    )

    return {
        "expired_count": expired_count,
        "error_count": error_count,
        "cutoff": cutoff.isoformat(),
    }


# ---------------------------------------------------------------------------
# Status notification task
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    name="app.tasks.kyc_tasks.send_status_notification",
    max_retries=3,
    default_retry_delay=30,
    queue="notifications",
)
def send_status_notification(
    self,
    submission_id: str,
    user_id: str,
    new_status: str,
    reason: str = "",
) -> Dict[str, Any]:
    """
    Send a notification to the user when their KYC status changes.

    Currently logs the notification.  In production this would:
    - Send an email via SMTP
    - Push a WebSocket event to connected clients
    - Trigger a webhook if configured

    Args:
        submission_id: KYC submission UUID.
        user_id:       User UUID.
        new_status:    New status/decision string.
        reason:        Optional reason text.
    """
    logger.info(
        "KYC status notification",
        submission_id=submission_id,
        user_id=user_id,
        new_status=new_status,
    )

    # TODO: integrate email / websocket / webhook here
    # Example:
    #   send_email(user_id=user_id, template="kyc_status_change",
    #              context={"status": new_status, "reason": reason})

    return {
        "submission_id": submission_id,
        "user_id": user_id,
        "status": new_status,
        "notification_sent": True,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mark_submission_error(submission_id: str, error_message: str) -> None:
    """Update KYCSubmission to UNDER_REVIEW state on unrecoverable task failure."""
    async def _update():
        from sqlalchemy import select  # noqa: PLC0415
        from app.core.database import AsyncSessionLocal  # noqa: PLC0415
        from app.models.kyc import KYCSubmission, KYCStatus, RiskLevel  # noqa: PLC0415

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(KYCSubmission).where(KYCSubmission.id == submission_id)
            )
            submission = result.scalar_one_or_none()
            if submission:
                submission.status = KYCStatus.UNDER_REVIEW
                submission.processing_error = error_message[:2000]
                submission.risk_level = RiskLevel.HIGH
                await session.commit()

    try:
        asyncio.run(_update())
    except Exception as exc:
        logger.error(
            "Failed to mark submission as error",
            submission_id=submission_id,
            error=str(exc),
        )
