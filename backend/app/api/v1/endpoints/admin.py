"""
Admin Endpoints

GET  /admin/kyc/submissions           – Paginated list with filters
GET  /admin/kyc/submissions/{id}      – Detailed view with AI scores
POST /admin/kyc/submissions/{id}/override – Manual decision override
GET  /admin/stats                     – Dashboard statistics
GET  /admin/users                     – User management list
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_admin, require_reviewer
from app.core.logging_config import get_logger
from app.models.kyc import KYCStatus, KYCSubmission, RiskLevel
from app.models.user import User, UserRole, UserStatus
from app.schemas.kyc import (
    KYCListResponse,
    KYCStatsResponse,
    KYCStatusUpdate,
    KYCSubmissionResponse,
    KYCSubmissionSummary,
)
from app.schemas.user import UserListResponse, UserResponse
from app.services.kyc_service import admin_override

router = APIRouter(prefix="/admin", tags=["Admin"])
logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# List KYC submissions (admin view with filters)
# ---------------------------------------------------------------------------


@router.get(
    "/kyc/submissions",
    response_model=KYCListResponse,
    summary="List all KYC submissions (admin)",
    description=(
        "Paginated list of all KYC submissions with optional filters "
        "for status, risk level, and date range."
    ),
)
async def admin_list_submissions(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    status_filter: Optional[KYCStatus] = Query(default=None, alias="status"),
    risk_level: Optional[RiskLevel] = Query(default=None),
    search: Optional[str] = Query(
        default=None, description="Search by applicant name or reference number"
    ),
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
    reviewer: User = Depends(require_reviewer),
    db: AsyncSession = Depends(get_db),
) -> KYCListResponse:
    """List all KYC submissions with optional filters."""
    offset = (page - 1) * size
    filters = []

    if status_filter:
        filters.append(KYCSubmission.status == status_filter)
    if risk_level:
        filters.append(KYCSubmission.risk_level == risk_level)
    if date_from:
        filters.append(KYCSubmission.created_at >= date_from)
    if date_to:
        filters.append(KYCSubmission.created_at <= date_to)
    if search:
        search_term = f"%{search}%"
        filters.append(
            (KYCSubmission.applicant_first_name.ilike(search_term))
            | (KYCSubmission.applicant_last_name.ilike(search_term))
            | (KYCSubmission.reference_number.ilike(search_term))
        )

    # Count
    count_stmt = select(func.count(KYCSubmission.id))
    if filters:
        from sqlalchemy import and_  # noqa: PLC0415
        count_stmt = count_stmt.where(and_(*filters))
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    # Items
    items_stmt = (
        select(KYCSubmission)
        .order_by(KYCSubmission.created_at.desc())
        .offset(offset)
        .limit(size)
    )
    if filters:
        from sqlalchemy import and_  # noqa: PLC0415
        items_stmt = items_stmt.where(and_(*filters))
    items_result = await db.execute(items_stmt)
    items = items_result.scalars().all()

    return KYCListResponse(
        items=[KYCSubmissionSummary.model_validate(s) for s in items],
        total=total,
        page=page,
        size=size,
        pages=math.ceil(total / size) if total > 0 else 0,
    )


# ---------------------------------------------------------------------------
# Get single submission (admin – full detail)
# ---------------------------------------------------------------------------


@router.get(
    "/kyc/submissions/{submission_id}",
    response_model=KYCSubmissionResponse,
    summary="Get full KYC submission details (admin)",
    description="Retrieve complete submission details including AI scores and fraud flags.",
)
async def admin_get_submission(
    submission_id: UUID,
    reviewer: User = Depends(require_reviewer),
    db: AsyncSession = Depends(get_db),
) -> KYCSubmissionResponse:
    """Retrieve a specific KYC submission for admin review."""
    result = await db.execute(
        select(KYCSubmission).where(KYCSubmission.id == submission_id)
    )
    submission: Optional[KYCSubmission] = result.scalar_one_or_none()
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="KYC submission not found.",
        )
    await db.refresh(submission)
    await db.refresh(submission, attribute_names=["user", "reviewer", "documents"])
    return KYCSubmissionResponse.from_model(submission)


# ---------------------------------------------------------------------------
# Manual override
# ---------------------------------------------------------------------------


@router.post(
    "/kyc/submissions/{submission_id}/override",
    response_model=KYCSubmissionResponse,
    summary="Manually override a KYC decision",
    description=(
        "Allow an admin or reviewer to manually approve, reject, or "
        "escalate a KYC submission. A reason is required."
    ),
)
async def admin_override_submission(
    submission_id: UUID,
    body: KYCStatusUpdate,
    reviewer: User = Depends(require_reviewer),
    db: AsyncSession = Depends(get_db),
) -> KYCSubmissionResponse:
    """Manually override the decision on a KYC submission."""
    # Map KYCStatus to decision string
    decision_map = {
        KYCStatus.APPROVED: "APPROVED",
        KYCStatus.REJECTED: "REJECTED",
        KYCStatus.UNDER_REVIEW: "MANUAL_REVIEW",
    }
    decision = decision_map.get(body.status)
    if not decision:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Status '{body.status.value}' is not a valid override target. "
                   "Use: approved, rejected, or under_review.",
        )

    reason = body.reason or body.reviewer_notes or "Manual override by reviewer."

    submission = await admin_override(
        db=db,
        submission_id=submission_id,
        admin_id=reviewer.id,
        decision=decision,
        reason=reason,
    )
    await db.commit()
    await db.refresh(submission)
    await db.refresh(submission, attribute_names=["user", "reviewer", "documents"])

    logger.info(
        "Admin override",
        submission_id=str(submission_id),
        reviewer_id=str(reviewer.id),
        decision=decision,
    )

    return KYCSubmissionResponse.from_model(submission)


# ---------------------------------------------------------------------------
# Dashboard statistics
# ---------------------------------------------------------------------------


@router.get(
    "/stats",
    response_model=KYCStatsResponse,
    summary="KYC dashboard statistics",
    description="Return aggregate statistics for the KYC dashboard.",
)
async def admin_stats(
    reviewer: User = Depends(require_reviewer),
    db: AsyncSession = Depends(get_db),
) -> KYCStatsResponse:
    """Return KYC processing statistics."""
    # Total submissions
    total_result = await db.execute(select(func.count(KYCSubmission.id)))
    total = total_result.scalar() or 0

    # By status
    status_result = await db.execute(
        select(KYCSubmission.status, func.count(KYCSubmission.id)).group_by(
            KYCSubmission.status
        )
    )
    by_status: Dict[str, int] = {row[0].value: row[1] for row in status_result.all()}

    # By risk level
    risk_result = await db.execute(
        select(KYCSubmission.risk_level, func.count(KYCSubmission.id))
        .where(KYCSubmission.risk_level.isnot(None))
        .group_by(KYCSubmission.risk_level)
    )
    by_risk: Dict[str, int] = {row[0].value: row[1] for row in risk_result.all()}

    # Auto-approved: approved with high confidence (no manual reviewer)
    auto_approved_result = await db.execute(
        select(func.count(KYCSubmission.id)).where(
            KYCSubmission.status == KYCStatus.APPROVED,
            KYCSubmission.reviewer_id.is_(None),
        )
    )
    auto_approved = auto_approved_result.scalar() or 0

    # Auto-rejected
    auto_rejected_result = await db.execute(
        select(func.count(KYCSubmission.id)).where(
            KYCSubmission.status == KYCStatus.REJECTED,
            KYCSubmission.reviewer_id.is_(None),
        )
    )
    auto_rejected = auto_rejected_result.scalar() or 0

    # Manual review
    manual_review = by_status.get("under_review", 0)

    # Average processing time
    avg_time_result = await db.execute(
        select(
            func.avg(
                func.extract(
                    "epoch",
                    KYCSubmission.processing_completed_at
                    - KYCSubmission.processing_started_at,
                )
            )
        ).where(
            KYCSubmission.processing_completed_at.isnot(None),
            KYCSubmission.processing_started_at.isnot(None),
        )
    )
    avg_processing_time = avg_time_result.scalar()

    # Approval rate
    approved_count = by_status.get("approved", 0)
    terminal_count = (
        by_status.get("approved", 0) + by_status.get("rejected", 0)
    )
    approval_rate = (
        round(approved_count / terminal_count, 4) if terminal_count > 0 else None
    )

    return KYCStatsResponse(
        total_submissions=total,
        by_status=by_status,
        by_risk_level=by_risk,
        auto_approved=auto_approved,
        auto_rejected=auto_rejected,
        manual_review=manual_review,
        avg_processing_time_seconds=(
            round(float(avg_processing_time), 2) if avg_processing_time else None
        ),
        approval_rate=approval_rate,
    )


# ---------------------------------------------------------------------------
# Submissions over time (chart data)
# ---------------------------------------------------------------------------


@router.get(
    "/stats/submissions-over-time",
    response_model=List[Dict[str, Any]],
    summary="Submissions over time chart data",
    description="Return daily submission counts for the past N days.",
)
async def submissions_over_time(
    days: int = Query(default=30, ge=1, le=365, description="Number of days to look back"),
    reviewer: User = Depends(require_reviewer),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Return daily submission counts for chart rendering."""
    end_date   = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    start_date = end_date - timedelta(days=days - 1)

    # Fetch all submissions in the date range
    result = await db.execute(
        select(KYCSubmission.created_at, KYCSubmission.status)
        .where(KYCSubmission.created_at >= start_date)
        .order_by(KYCSubmission.created_at)
    )
    rows = result.all()

    # Build a dict of day → counts
    daily: Dict[str, Dict[str, int]] = {}
    current = start_date
    while current <= end_date:
        day_str = current.strftime("%Y-%m-%d")
        daily[day_str] = {"total": 0, "approved": 0, "rejected": 0, "pending": 0}
        current += timedelta(days=1)

    for created_at, status in rows:
        day_str = created_at.strftime("%Y-%m-%d")
        if day_str in daily:
            daily[day_str]["total"] += 1
            if status == KYCStatus.APPROVED:
                daily[day_str]["approved"] += 1
            elif status == KYCStatus.REJECTED:
                daily[day_str]["rejected"] += 1
            else:
                daily[day_str]["pending"] += 1

    return [{"date": day, **counts} for day, counts in sorted(daily.items())]


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------


@router.get(
    "/users",
    response_model=UserListResponse,
    summary="List all users (admin)",
    description="Paginated list of all users with optional role/status filters.",
)
async def admin_list_users(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    role: Optional[UserRole] = Query(default=None),
    user_status: Optional[UserStatus] = Query(default=None, alias="status"),
    search: Optional[str] = Query(
        default=None, description="Search by email or username"
    ),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserListResponse:
    """List all user accounts (admin only)."""
    offset = (page - 1) * size
    filters = [User.deleted_at.is_(None)]

    if role:
        filters.append(User.role == role)
    if user_status:
        filters.append(User.status == user_status)
    if search:
        search_term = f"%{search}%"
        filters.append(
            User.email.ilike(search_term) | User.username.ilike(search_term)
        )

    from sqlalchemy import and_  # noqa: PLC0415

    count_result = await db.execute(
        select(func.count(User.id)).where(and_(*filters))
    )
    total = count_result.scalar() or 0

    items_result = await db.execute(
        select(User)
        .where(and_(*filters))
        .order_by(User.created_at.desc())
        .offset(offset)
        .limit(size)
    )
    items = items_result.scalars().all()

    return UserListResponse(
        items=[UserResponse.from_model(u) for u in items],
        total=total,
        page=page,
        size=size,
        pages=math.ceil(total / size) if total > 0 else 0,
    )
