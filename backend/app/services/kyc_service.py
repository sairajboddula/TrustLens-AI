"""
KYC Service

Business logic for KYC submission lifecycle management:
  - Creating and submitting KYC applications
  - Retrieving submission status
  - Listing a user's submissions (paginated)
  - Admin decision override
  - Invoking the LangGraph agent pipeline via Celery
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging_config import get_logger
from app.models.kyc import KYCStatus, KYCSubmission, RiskLevel
from app.models.user import User

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Reference number generator
# ---------------------------------------------------------------------------


async def _next_reference_number(db: AsyncSession) -> str:
    """Generate a sequential KYC reference number: KYC-YYYY-NNNNNN."""
    year = datetime.now(timezone.utc).year
    count_result = await db.execute(
        select(func.count(KYCSubmission.id)).where(
            func.extract("year", KYCSubmission.created_at) == year
        )
    )
    count = (count_result.scalar() or 0) + 1
    return f"KYC-{year}-{count:06d}"


# ---------------------------------------------------------------------------
# Submit KYC
# ---------------------------------------------------------------------------


async def submit_kyc(
    db: AsyncSession,
    user_id: str | UUID,
    form_data: Dict[str, Any],
    document_ids: List[str],
) -> KYCSubmission:
    """
    Create a new KYC submission record and trigger the agent pipeline.

    Steps:
      1. Validate submission limits per user
      2. Create KYCSubmission in SUBMITTED state
      3. Dispatch Celery task to run the LangGraph graph
      4. Store Celery task ID on the record

    Args:
        db:           Async DB session.
        user_id:      UUID of the submitting user.
        form_data:    Dict of applicant fields (first_name, last_name, dob, …)
        document_ids: List of Document UUIDs already uploaded.

    Returns:
        Created KYCSubmission instance.

    Raises:
        HTTPException 400: If submission limit exceeded.
        HTTPException 404: If user not found.
    """
    from app.core.config import settings  # noqa: PLC0415

    user_result = await db.execute(select(User).where(User.id == user_id))
    user: Optional[User] = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    # Check submission limit
    active_count_result = await db.execute(
        select(func.count(KYCSubmission.id)).where(
            KYCSubmission.user_id == user_id,
            KYCSubmission.status.notin_(
                [KYCStatus.REJECTED, KYCStatus.CANCELLED, KYCStatus.EXPIRED]
            ),
        )
    )
    active_count = active_count_result.scalar() or 0
    if active_count >= settings.KYC_MAX_SUBMISSION_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Maximum KYC submission attempts reached ({settings.KYC_MAX_SUBMISSION_ATTEMPTS}). "
                "Please contact support."
            ),
        )

    reference_number = await _next_reference_number(db)

    # Map form_data to model fields
    submission = KYCSubmission(
        user_id=user_id,
        reference_number=reference_number,
        applicant_first_name=form_data.get("first_name", "").strip().title(),
        applicant_last_name=form_data.get("last_name", "").strip().title(),
        applicant_date_of_birth=_parse_dob(form_data.get("date_of_birth")),
        applicant_nationality=form_data.get("nationality"),
        applicant_address=form_data.get("address"),
        applicant_phone=form_data.get("phone"),
        applicant_email=form_data.get("email"),
        primary_document_type=form_data.get("id_type", "passport"),
        primary_document_number=form_data.get("id_number") or None,
        primary_document_expiry=_parse_dob(form_data.get("document_expiry")),
        status=KYCStatus.SUBMITTED,
        submitted_at=datetime.now(timezone.utc),
        processing_attempts=0,
    )

    db.add(submission)
    await db.flush()   # Get submission.id

    logger.info(
        "KYC submission created",
        submission_id=str(submission.id),
        reference=reference_number,
        user_id=str(user_id),
    )

    # Dispatch async processing via Celery
    task_id: Optional[str] = await _dispatch_celery_task(
        submission_id=str(submission.id),
        user_id=str(user_id),
        form_data=form_data,
        document_ids=document_ids,
    )
    if task_id:
        submission.celery_task_id = task_id
        submission.status = KYCStatus.PROCESSING
        submission.processing_started_at = datetime.now(timezone.utc)

    await db.flush()
    return submission


def _parse_dob(dob_str: Optional[str]) -> Optional[datetime]:
    """Parse YYYY-MM-DD string to datetime, or return None."""
    if not dob_str:
        return None
    try:
        return datetime.strptime(dob_str.strip(), "%Y-%m-%d").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None


async def _dispatch_celery_task(
    submission_id: str,
    user_id: str,
    form_data: Dict[str, Any],
    document_ids: List[str],
) -> Optional[str]:
    """
    Dispatch the process_kyc_submission Celery task.

    Returns the Celery task ID, or None if Celery is unavailable.
    """
    try:
        from app.tasks.kyc_tasks import process_kyc_submission  # noqa: PLC0415

        task = process_kyc_submission.delay(
            submission_id=submission_id,
            user_id=user_id,
            form_data=form_data,
            document_ids=document_ids,
        )
        logger.info(
            "Celery task dispatched",
            task_id=task.id,
            submission_id=submission_id,
        )
        return task.id
    except Exception as exc:
        logger.error(
            "Failed to dispatch Celery task – processing will be skipped",
            submission_id=submission_id,
            error=str(exc),
        )
        return None


# ---------------------------------------------------------------------------
# Status retrieval
# ---------------------------------------------------------------------------


async def get_submission_status(
    db: AsyncSession,
    submission_id: str | UUID,
    user_id: str | UUID,
) -> KYCSubmission:
    """
    Retrieve a single KYC submission, enforcing ownership.

    Raises:
        HTTPException 404: If submission not found or belongs to another user.
    """
    result = await db.execute(
        select(KYCSubmission).where(
            KYCSubmission.id == submission_id,
            KYCSubmission.user_id == user_id,
        )
    )
    submission: Optional[KYCSubmission] = result.scalar_one_or_none()
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="KYC submission not found.",
        )
    return submission


# ---------------------------------------------------------------------------
# List submissions (paginated)
# ---------------------------------------------------------------------------


async def list_user_submissions(
    db: AsyncSession,
    user_id: str | UUID,
    page: int = 1,
    size: int = 20,
) -> Dict[str, Any]:
    """
    Return a paginated list of KYC submissions for *user_id*.

    Returns:
        Dict with keys: items, total, page, size, pages.
    """
    offset = (page - 1) * size

    # Total count
    count_result = await db.execute(
        select(func.count(KYCSubmission.id)).where(
            KYCSubmission.user_id == user_id
        )
    )
    total = count_result.scalar() or 0

    # Paginated items
    items_result = await db.execute(
        select(KYCSubmission)
        .where(KYCSubmission.user_id == user_id)
        .order_by(KYCSubmission.created_at.desc())
        .offset(offset)
        .limit(size)
    )
    items = items_result.scalars().all()

    return {
        "items": list(items),
        "total": total,
        "page": page,
        "size": size,
        "pages": math.ceil(total / size) if total > 0 else 0,
    }


# ---------------------------------------------------------------------------
# Admin override
# ---------------------------------------------------------------------------


async def admin_override(
    db: AsyncSession,
    submission_id: str | UUID,
    admin_id: str | UUID,
    decision: str,   # APPROVED | REJECTED | MANUAL_REVIEW
    reason: str,
) -> KYCSubmission:
    """
    Allow an admin/reviewer to manually override the KYC decision.

    Args:
        db:            Async DB session.
        submission_id: Target KYC submission ID.
        admin_id:      ID of the admin performing the override.
        decision:      New decision string.
        reason:        Mandatory reason/notes.

    Returns:
        Updated KYCSubmission.

    Raises:
        HTTPException 404: Submission not found.
        HTTPException 400: Invalid decision value.
    """
    valid_decisions = {"APPROVED", "REJECTED", "MANUAL_REVIEW"}
    if decision.upper() not in valid_decisions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid decision '{decision}'. Must be one of: {valid_decisions}",
        )

    result = await db.execute(
        select(KYCSubmission).where(KYCSubmission.id == submission_id)
    )
    submission: Optional[KYCSubmission] = result.scalar_one_or_none()
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="KYC submission not found."
        )

    status_map = {
        "APPROVED": KYCStatus.APPROVED,
        "REJECTED": KYCStatus.REJECTED,
        "MANUAL_REVIEW": KYCStatus.UNDER_REVIEW,
    }
    now = datetime.now(timezone.utc)

    submission.status = status_map[decision.upper()]
    submission.status_reason = reason
    submission.reviewer_id = admin_id
    submission.reviewer_notes = reason
    submission.reviewed_at = now

    if decision.upper() == "REJECTED":
        submission.rejection_reasons = [reason]

    await db.flush()

    logger.info(
        "Admin KYC override",
        submission_id=str(submission_id),
        admin_id=str(admin_id),
        new_decision=decision,
    )
    return submission


# ---------------------------------------------------------------------------
# Run KYC graph (async, for direct invocation without Celery)
# ---------------------------------------------------------------------------


async def run_kyc_graph(
    submission_id: str,
    state: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Invoke the LangGraph KYC pipeline asynchronously.

    Useful for direct API-driven invocation (e.g. testing, admin re-runs).

    Args:
        submission_id: KYC submission UUID string.
        state:         Initial KYCAgentState dict.

    Returns:
        Final KYCAgentState dict after the graph completes.
    """
    import asyncio  # noqa: PLC0415

    from app.graph.kyc_graph import get_kyc_graph  # noqa: PLC0415

    graph = get_kyc_graph()

    logger.info("Running KYC graph directly", submission_id=submission_id)

    # LangGraph's compiled graph .invoke() is synchronous; run in thread pool
    final_state = await asyncio.to_thread(graph.invoke, state)

    logger.info(
        "KYC graph completed",
        submission_id=submission_id,
        decision=final_state.get("decision"),
        confidence=final_state.get("confidence_score"),
    )
    return final_state
