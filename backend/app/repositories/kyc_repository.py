"""
KYC Application - KYC Repository

Data access layer for KYC submission model operations.
Handles workflow state transitions, statistics, and
reviewer assignment logic.
"""

import random
import string
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, func, or_, select, update

from app.core.config import settings
from app.core.logging_config import get_logger
from app.models.kyc import KYCDocumentType, KYCStatus, KYCSubmission, RiskLevel
from app.repositories.base import BaseRepository

logger = get_logger(__name__)


class KYCRepository(BaseRepository[KYCSubmission]):
    """
    Repository for KYC submission database operations.

    Manages the full KYC workflow including status transitions,
    reviewer assignment, statistics, and reporting queries.
    """

    def __init__(self, session):
        super().__init__(KYCSubmission, session)

    # =========================================================================
    # Reference Number Generation
    # =========================================================================

    @staticmethod
    def _generate_reference_number() -> str:
        """
        Generate a unique human-readable reference number.

        Format: KYC-YYYY-XXXXXXXX (8 alphanumeric chars)
        Example: KYC-2024-A3B7C9D2
        """
        year = datetime.now(timezone.utc).year
        suffix = "".join(
            random.choices(string.ascii_uppercase + string.digits, k=8)
        )
        return f"KYC-{year}-{suffix}"

    async def generate_unique_reference(self) -> str:
        """
        Generate a reference number guaranteed to be unique in the database.

        Retries up to 10 times to avoid collisions.
        """
        for _ in range(10):
            ref = self._generate_reference_number()
            exists = await self.exists_by_field("reference_number", ref)
            if not exists:
                return ref
        raise RuntimeError("Failed to generate unique reference number after 10 attempts")

    # =========================================================================
    # Creation
    # =========================================================================

    async def create_submission(
        self,
        user_id: UUID,
        applicant_first_name: str,
        applicant_last_name: str,
        primary_document_type: KYCDocumentType,
        **kwargs,
    ) -> KYCSubmission:
        """
        Create a new KYC submission in DRAFT status.

        Args:
            user_id: ID of the submitting user
            applicant_first_name: First name
            applicant_last_name: Last name
            primary_document_type: Type of primary document
            **kwargs: Additional fields

        Returns:
            Newly created KYCSubmission
        """
        reference_number = await self.generate_unique_reference()

        data = {
            "user_id": user_id,
            "reference_number": reference_number,
            "applicant_first_name": applicant_first_name,
            "applicant_last_name": applicant_last_name,
            "primary_document_type": primary_document_type,
            "status": KYCStatus.DRAFT,
            **kwargs,
        }

        submission = await self.create(data)
        logger.info(
            "KYC submission created",
            submission_id=str(submission.id),
            reference=submission.reference_number,
            user_id=str(user_id),
        )
        return submission

    # =========================================================================
    # Status Transitions
    # =========================================================================

    async def submit(self, submission_id: UUID) -> Optional[KYCSubmission]:
        """
        Transition a DRAFT submission to SUBMITTED status.

        Args:
            submission_id: ID of the submission to submit

        Returns:
            Updated KYCSubmission, or None if not found
        """
        return await self.update(
            submission_id,
            {
                "status": KYCStatus.SUBMITTED,
                "submitted_at": datetime.now(timezone.utc),
            },
        )

    async def start_processing(self, submission_id: UUID) -> Optional[KYCSubmission]:
        """
        Transition to PROCESSING status when AI/OCR starts.

        Args:
            submission_id: ID of the submission

        Returns:
            Updated KYCSubmission
        """
        return await self.update(
            submission_id,
            {
                "status": KYCStatus.PROCESSING,
                "processing_started_at": datetime.now(timezone.utc),
            },
        )

    async def mark_under_review(
        self,
        submission_id: UUID,
    ) -> Optional[KYCSubmission]:
        """
        Transition to UNDER_REVIEW after processing requires human review.

        Args:
            submission_id: ID of the submission

        Returns:
            Updated KYCSubmission
        """
        return await self.update(
            submission_id,
            {
                "status": KYCStatus.UNDER_REVIEW,
                "processing_completed_at": datetime.now(timezone.utc),
            },
        )

    async def approve(
        self,
        submission_id: UUID,
        reviewer_id: UUID,
        notes: Optional[str] = None,
        validity_days: int = 365,
    ) -> Optional[KYCSubmission]:
        """
        Approve a KYC submission.

        Args:
            submission_id: ID of the submission
            reviewer_id: ID of the reviewing user
            notes: Optional reviewer notes
            validity_days: How many days the approval is valid for

        Returns:
            Updated KYCSubmission
        """
        from datetime import timedelta
        now = datetime.now(timezone.utc)

        return await self.update(
            submission_id,
            {
                "status": KYCStatus.APPROVED,
                "reviewer_id": reviewer_id,
                "reviewed_at": now,
                "reviewer_notes": notes,
                "expires_at": now + timedelta(days=validity_days),
                "processing_completed_at": now,
            },
        )

    async def reject(
        self,
        submission_id: UUID,
        reviewer_id: UUID,
        reason: str,
        rejection_reasons: Optional[List[str]] = None,
        notes: Optional[str] = None,
    ) -> Optional[KYCSubmission]:
        """
        Reject a KYC submission.

        Args:
            submission_id: ID of the submission
            reviewer_id: ID of the reviewing user
            reason: Main rejection reason
            rejection_reasons: Structured list of rejection reasons
            notes: Internal reviewer notes

        Returns:
            Updated KYCSubmission
        """
        now = datetime.now(timezone.utc)
        return await self.update(
            submission_id,
            {
                "status": KYCStatus.REJECTED,
                "reviewer_id": reviewer_id,
                "reviewed_at": now,
                "status_reason": reason,
                "rejection_reasons": rejection_reasons or [reason],
                "reviewer_notes": notes,
                "processing_completed_at": now,
            },
        )

    async def cancel(self, submission_id: UUID) -> Optional[KYCSubmission]:
        """Cancel a KYC submission."""
        return await self.update(
            submission_id,
            {"status": KYCStatus.CANCELLED},
        )

    async def record_processing_result(
        self,
        submission_id: UUID,
        ai_confidence_score: float,
        ai_document_authenticity_score: Optional[float],
        ai_face_match_score: Optional[float],
        ai_liveness_score: Optional[float],
        ai_fraud_risk_score: Optional[float],
        ai_extracted_data: Optional[Dict[str, Any]],
        ai_verification_details: Optional[Dict[str, Any]],
        ai_flags: Optional[List[str]],
        risk_level: Optional[RiskLevel],
        risk_factors: Optional[List[str]],
        extracted_document_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[KYCSubmission]:
        """
        Store AI/OCR processing results and determine next status.

        Uses configured thresholds to auto-approve, auto-reject,
        or flag for manual review.

        Args:
            submission_id: Submission to update
            ai_confidence_score: Overall confidence (0.0-1.0)
            (other AI scores and data...)

        Returns:
            Updated KYCSubmission with new status
        """
        now = datetime.now(timezone.utc)

        # Determine status based on confidence thresholds
        if ai_confidence_score >= settings.KYC_AUTO_APPROVE_THRESHOLD:
            new_status = KYCStatus.APPROVED
            expires_at = None  # Set by approve() method
        elif ai_confidence_score <= settings.KYC_AUTO_REJECT_THRESHOLD:
            new_status = KYCStatus.REJECTED
            expires_at = None
        else:
            new_status = KYCStatus.UNDER_REVIEW
            expires_at = None

        update_data: Dict[str, Any] = {
            "status": new_status,
            "processing_completed_at": now,
            "ai_confidence_score": ai_confidence_score,
            "ai_document_authenticity_score": ai_document_authenticity_score,
            "ai_face_match_score": ai_face_match_score,
            "ai_liveness_score": ai_liveness_score,
            "ai_fraud_risk_score": ai_fraud_risk_score,
            "ai_extracted_data": ai_extracted_data,
            "ai_verification_details": ai_verification_details,
            "ai_flags": ai_flags,
            "risk_level": risk_level,
            "risk_factors": risk_factors,
        }

        # If auto-approved, set expiry
        if new_status == KYCStatus.APPROVED:
            from datetime import timedelta
            update_data["expires_at"] = now + timedelta(
                days=settings.KYC_DOCUMENT_EXPIRY_DAYS
            )
            update_data["reviewed_at"] = now
            update_data["status_reason"] = "Auto-approved by AI verification"

        # If auto-rejected, set reason
        elif new_status == KYCStatus.REJECTED:
            update_data["reviewed_at"] = now
            update_data["status_reason"] = "Auto-rejected: insufficient confidence score"

        # Update extracted document fields
        if extracted_document_data:
            update_data.update({
                "primary_document_number": extracted_document_data.get("document_number"),
                "primary_document_issuing_country": extracted_document_data.get("issuing_country"),
                "primary_document_expiry": extracted_document_data.get("expiry_date"),
            })

        return await self.update(submission_id, update_data)

    async def record_processing_error(
        self,
        submission_id: UUID,
        error_message: str,
    ) -> Optional[KYCSubmission]:
        """Record a processing failure."""
        submission = await self.get_by_id(submission_id)
        if submission is None:
            return None

        return await self.update(
            submission_id,
            {
                "processing_error": error_message,
                "processing_attempts": submission.processing_attempts + 1,
                "status": KYCStatus.SUBMITTED,  # Reset to submitted for retry
            },
        )

    async def set_celery_task_id(
        self, submission_id: UUID, task_id: str
    ) -> None:
        """Store the Celery task ID for tracking."""
        await self.update(submission_id, {"celery_task_id": task_id})

    # =========================================================================
    # Query Methods
    # =========================================================================

    async def get_by_reference_number(self, reference_number: str) -> Optional[KYCSubmission]:
        """Get a submission by its reference number."""
        return await self.get_by_field("reference_number", reference_number)

    async def get_user_submissions(
        self,
        user_id: UUID,
        page: int = 1,
        size: int = 20,
        status: Optional[KYCStatus] = None,
    ) -> Dict[str, Any]:
        """
        Get paginated KYC submissions for a specific user.

        Args:
            user_id: User ID to filter by
            page: Page number
            size: Items per page
            status: Optional status filter

        Returns:
            Paginated results
        """
        stmt = select(KYCSubmission).where(KYCSubmission.user_id == user_id)

        if status:
            stmt = stmt.where(KYCSubmission.status == status)

        stmt = stmt.order_by(KYCSubmission.created_at.desc())
        return await self.paginate(stmt, page=page, size=size)

    async def get_pending_review(
        self,
        page: int = 1,
        size: int = 20,
    ) -> Dict[str, Any]:
        """Get submissions awaiting manual review."""
        stmt = (
            select(KYCSubmission)
            .where(KYCSubmission.status == KYCStatus.UNDER_REVIEW)
            .order_by(KYCSubmission.processing_completed_at.asc())  # Oldest first
        )
        return await self.paginate(stmt, page=page, size=size)

    async def get_all_paginated(
        self,
        page: int = 1,
        size: int = 20,
        status: Optional[KYCStatus] = None,
        risk_level: Optional[RiskLevel] = None,
        search: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get all submissions with filtering and pagination.

        Args:
            page: Page number
            size: Items per page
            status: Filter by status
            risk_level: Filter by risk level
            search: Search by reference number or applicant name

        Returns:
            Paginated results
        """
        stmt = select(KYCSubmission)

        if status:
            stmt = stmt.where(KYCSubmission.status == status)

        if risk_level:
            stmt = stmt.where(KYCSubmission.risk_level == risk_level)

        if search:
            search_term = f"%{search.lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(KYCSubmission.reference_number).like(search_term),
                    func.lower(KYCSubmission.applicant_first_name).like(search_term),
                    func.lower(KYCSubmission.applicant_last_name).like(search_term),
                )
            )

        stmt = stmt.order_by(KYCSubmission.created_at.desc())
        return await self.paginate(stmt, page=page, size=size)

    async def get_user_active_submission(
        self, user_id: UUID
    ) -> Optional[KYCSubmission]:
        """
        Get the user's most recent non-terminal submission.

        Users should only have one active submission at a time.
        """
        terminal_statuses = [
            KYCStatus.APPROVED,
            KYCStatus.REJECTED,
            KYCStatus.EXPIRED,
            KYCStatus.CANCELLED,
        ]
        stmt = (
            select(KYCSubmission)
            .where(
                and_(
                    KYCSubmission.user_id == user_id,
                    KYCSubmission.status.notin_(terminal_statuses),
                )
            )
            .order_by(KYCSubmission.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def count_user_submissions(
        self,
        user_id: UUID,
    ) -> int:
        """Count total KYC submissions for a user."""
        stmt = select(func.count(KYCSubmission.id)).where(
            KYCSubmission.user_id == user_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    # =========================================================================
    # Statistics
    # =========================================================================

    async def get_statistics(self) -> Dict[str, Any]:
        """
        Get aggregate KYC processing statistics.

        Returns:
            Dictionary of statistics including counts by status/risk,
            processing times, and approval rates.
        """
        # Count by status
        status_stmt = (
            select(KYCSubmission.status, func.count(KYCSubmission.id))
            .group_by(KYCSubmission.status)
        )
        status_result = await self.session.execute(status_stmt)
        by_status = {row[0]: row[1] for row in status_result.all()}

        # Count by risk level
        risk_stmt = (
            select(KYCSubmission.risk_level, func.count(KYCSubmission.id))
            .where(KYCSubmission.risk_level.isnot(None))
            .group_by(KYCSubmission.risk_level)
        )
        risk_result = await self.session.execute(risk_stmt)
        by_risk = {row[0]: row[1] for row in risk_result.all()}

        # Total
        total = sum(by_status.values())

        # Approval rate
        approved = by_status.get(KYCStatus.APPROVED, 0)
        rejected = by_status.get(KYCStatus.REJECTED, 0)
        total_decided = approved + rejected
        approval_rate = (approved / total_decided) if total_decided > 0 else None

        return {
            "total_submissions": total,
            "by_status": {k.value if hasattr(k, "value") else k: v for k, v in by_status.items()},
            "by_risk_level": {k.value if hasattr(k, "value") else k: v for k, v in by_risk.items()},
            "auto_approved": by_status.get(KYCStatus.APPROVED, 0),
            "auto_rejected": by_status.get(KYCStatus.REJECTED, 0),
            "manual_review": by_status.get(KYCStatus.UNDER_REVIEW, 0),
            "approval_rate": approval_rate,
        }
