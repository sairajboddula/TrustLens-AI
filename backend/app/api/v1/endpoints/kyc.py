"""
KYC Submission Endpoints

POST /kyc/submit                      – Submit a new KYC application
GET  /kyc/submissions                 – List authenticated user's submissions
GET  /kyc/submissions/{id}            – Get full submission details
GET  /kyc/submissions/{id}/status     – Get lightweight processing status
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.core.logging_config import get_logger
from app.models.user import User
from app.schemas.kyc import (
    KYCListResponse,
    KYCSubmissionCreate,
    KYCSubmissionResponse,
    KYCSubmissionSummary,
)
from app.services.kyc_service import (
    get_submission_status,
    list_user_submissions,
    submit_kyc,
)

router = APIRouter(prefix="/kyc", tags=["KYC"])
logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Submit KYC application
# ---------------------------------------------------------------------------


@router.post(
    "/submit",
    response_model=KYCSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a new KYC application",
    description=(
        "Create a new KYC submission and trigger automated verification. "
        "Provide applicant details and a list of already-uploaded document IDs."
    ),
)
async def submit_kyc_application(
    body: KYCSubmissionCreate,
    document_ids: List[str] = Query(
        default=[],
        description="UUIDs of documents already uploaded via POST /documents/upload",
    ),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> KYCSubmissionResponse:
    """Submit a new KYC application for the authenticated user."""
    # Build form_data dict from the Pydantic schema
    form_data: Dict[str, Any] = {
        "first_name": body.applicant_first_name,
        "last_name": body.applicant_last_name,
        "date_of_birth": (
            body.applicant_date_of_birth.strftime("%Y-%m-%d")
            if body.applicant_date_of_birth
            else None
        ),
        "nationality": body.applicant_nationality,
        "address": body.applicant_address,
        "phone": body.applicant_phone,
        "email": body.applicant_email,
        "id_type": body.primary_document_type.value,
        "id_number": body.primary_document_number or "",
        "issuing_country": body.primary_document_issuing_country,
        "document_expiry": (
            body.primary_document_expiry.strftime("%Y-%m-%d")
            if body.primary_document_expiry
            else None
        ),
    }

    submission = await submit_kyc(
        db=db,
        user_id=current_user.id,
        form_data=form_data,
        document_ids=document_ids,
    )
    await db.commit()
    # 1) Reload all column attributes (flush expires server-side fields like updated_at)
    await db.refresh(submission)
    # 2) Eagerly load relationships so from_model() can access them synchronously
    await db.refresh(submission, attribute_names=["user", "reviewer", "documents"])

    logger.info(
        "KYC submitted via API",
        submission_id=str(submission.id),
        user_id=str(current_user.id),
    )

    return KYCSubmissionResponse.from_model(submission)


# ---------------------------------------------------------------------------
# List submissions
# ---------------------------------------------------------------------------


@router.get(
    "/submissions",
    response_model=KYCListResponse,
    summary="List current user's KYC submissions",
    description="Return a paginated list of all KYC submissions for the authenticated user.",
)
async def list_submissions(
    page: int = Query(default=1, ge=1, description="Page number"),
    size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> KYCListResponse:
    """List KYC submissions for the authenticated user."""
    result = await list_user_submissions(
        db=db,
        user_id=current_user.id,
        page=page,
        size=size,
    )

    return KYCListResponse(
        items=[KYCSubmissionSummary.model_validate(s) for s in result["items"]],
        total=result["total"],
        page=result["page"],
        size=result["size"],
        pages=result["pages"],
    )


# ---------------------------------------------------------------------------
# Get submission details
# ---------------------------------------------------------------------------


@router.get(
    "/submissions/{submission_id}",
    response_model=KYCSubmissionResponse,
    summary="Get full KYC submission details",
    description=(
        "Return complete details for a specific KYC submission, "
        "including AI scores and document information. "
        "Users can only retrieve their own submissions."
    ),
)
async def get_submission(
    submission_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> KYCSubmissionResponse:
    """Retrieve a KYC submission by ID."""
    submission = await get_submission_status(
        db=db,
        submission_id=submission_id,
        user_id=current_user.id,
    )
    await db.refresh(submission)
    await db.refresh(submission, attribute_names=["user", "reviewer", "documents"])
    return KYCSubmissionResponse.from_model(submission)


# ---------------------------------------------------------------------------
# Get processing status (lightweight)
# ---------------------------------------------------------------------------


@router.get(
    "/submissions/{submission_id}/status",
    response_model=Dict[str, Any],
    summary="Get KYC submission processing status",
    description=(
        "Lightweight endpoint returning only the current status and key scores. "
        "Suitable for polling while waiting for processing to complete."
    ),
)
async def get_submission_status_view(
    submission_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Return the current processing status of a KYC submission."""
    submission = await get_submission_status(
        db=db,
        submission_id=submission_id,
        user_id=current_user.id,
    )

    return {
        "submission_id": str(submission.id),
        "reference_number": submission.reference_number,
        "status": submission.status.value,
        "risk_level": submission.risk_level.value if submission.risk_level else None,
        "ai_confidence_score": submission.ai_confidence_score,
        "submitted_at": (
            submission.submitted_at.isoformat() if submission.submitted_at else None
        ),
        "processing_started_at": (
            submission.processing_started_at.isoformat()
            if submission.processing_started_at
            else None
        ),
        "processing_completed_at": (
            submission.processing_completed_at.isoformat()
            if submission.processing_completed_at
            else None
        ),
        "celery_task_id": submission.celery_task_id,
    }
