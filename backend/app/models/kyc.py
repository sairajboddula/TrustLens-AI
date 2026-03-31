"""
KYC Application - KYC Submission Model

SQLAlchemy ORM model representing a KYC application submission
with workflow status, AI verification results, and risk scoring.
"""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.document import Document
    from app.models.audit_log import AuditLog
    from app.models.workflow import KYCWorkflowStep, KYCFinalReport, KYCAdminDecision, KYCTimeline


# =============================================================================
# Enumerations
# =============================================================================

class KYCStatus(str, enum.Enum):
    """
    KYC submission workflow status.

    Status flow:
    DRAFT → SUBMITTED → PROCESSING → UNDER_REVIEW → APPROVED
                                  ↓              ↓
                               REJECTED      REJECTED
    """
    DRAFT = "draft"                     # Not yet submitted
    SUBMITTED = "submitted"             # Submitted, awaiting processing
    PROCESSING = "processing"           # AI/OCR processing in progress
    UNDER_REVIEW = "under_review"       # Requires manual human review
    APPROVED = "approved"               # KYC approved
    REJECTED = "rejected"               # KYC rejected
    EXPIRED = "expired"                 # Submission expired without completion
    CANCELLED = "cancelled"             # Cancelled by user


class KYCDocumentType(str, enum.Enum):
    """Types of identity documents accepted for KYC."""
    PASSPORT = "passport"
    NATIONAL_ID = "national_id"
    DRIVERS_LICENSE = "drivers_license"
    RESIDENCE_PERMIT = "residence_permit"
    UTILITY_BILL = "utility_bill"
    BANK_STATEMENT = "bank_statement"
    TAX_DOCUMENT = "tax_document"
    SELFIE = "selfie"


class RiskLevel(str, enum.Enum):
    """Risk classification for KYC submissions."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


# =============================================================================
# KYC Submission Model
# =============================================================================

class KYCSubmission(Base):
    """
    KYC Application Submission model.

    Tracks the full lifecycle of a KYC verification request from
    initial submission through AI processing to final decision.
    Stores AI verification results, risk scores, and review notes.
    """

    __tablename__ = "kyc_submissions"

    __table_args__ = (
        Index("ix_kyc_user_id", "user_id"),
        Index("ix_kyc_status", "status"),
        Index("ix_kyc_risk_level", "risk_level"),
        Index("ix_kyc_created_at", "created_at"),
        Index("ix_kyc_reviewer_id", "reviewer_id"),
        Index("ix_kyc_reference_number", "reference_number"),
        {"schema": None},
    )

    # -------------------------------------------------------------------------
    # Primary Key
    # -------------------------------------------------------------------------
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique KYC submission identifier (UUID v4)",
    )

    # -------------------------------------------------------------------------
    # Reference
    # -------------------------------------------------------------------------
    reference_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
        comment="Human-readable reference number (e.g., KYC-2024-001234)",
    )

    # -------------------------------------------------------------------------
    # Relationships (Foreign Keys)
    # -------------------------------------------------------------------------
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="ID of the user who submitted this KYC",
    )
    reviewer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="ID of the reviewer who made the final decision",
    )

    # -------------------------------------------------------------------------
    # Applicant Information (captured at submission time)
    # -------------------------------------------------------------------------
    applicant_first_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Applicant's first name as submitted",
    )
    applicant_last_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Applicant's last name as submitted",
    )
    applicant_date_of_birth: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Applicant's date of birth",
    )
    applicant_nationality: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Applicant's nationality (country name or ISO 3166-1 alpha-3)",
    )
    applicant_address: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Applicant's full address",
    )
    applicant_phone: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Applicant's phone number",
    )
    applicant_email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Applicant's email address",
    )

    # -------------------------------------------------------------------------
    # Document Information
    # -------------------------------------------------------------------------
    primary_document_type: Mapped[KYCDocumentType] = mapped_column(
        Enum(KYCDocumentType, name="kyc_document_type_enum", create_type=False,
             values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        comment="Type of primary identity document",
    )
    primary_document_number: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Document number/ID from primary document",
    )
    primary_document_issuing_country: Mapped[Optional[str]] = mapped_column(
        String(3),
        nullable=True,
        comment="Issuing country of primary document (ISO 3166-1 alpha-3)",
    )
    primary_document_expiry: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Expiry date of primary document",
    )

    # -------------------------------------------------------------------------
    # Status & Workflow
    # -------------------------------------------------------------------------
    status: Mapped[KYCStatus] = mapped_column(
        Enum(KYCStatus, name="kyc_status_enum", create_type=False,
             values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=KYCStatus.DRAFT,
        comment="Current workflow status",
    )
    status_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for current status (especially for rejections)",
    )
    submitted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the submission was formally submitted",
    )
    processing_started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When AI processing began",
    )
    processing_completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When AI processing completed",
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When a reviewer made the final decision",
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the KYC approval expires (for approved submissions)",
    )

    # -------------------------------------------------------------------------
    # AI Verification Results
    # -------------------------------------------------------------------------
    ai_confidence_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Overall AI confidence score (0.0-1.0)",
    )
    ai_document_authenticity_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Document authenticity confidence score (0.0-1.0)",
    )
    ai_face_match_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Face-to-document match confidence score (0.0-1.0)",
    )
    ai_liveness_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Liveness detection confidence score (0.0-1.0)",
    )
    ai_fraud_risk_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Fraud risk score (0.0=low risk, 1.0=high risk)",
    )
    ai_extracted_data: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="JSON blob of data extracted from documents by AI/OCR",
    )
    ai_verification_details: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Detailed AI verification results and checks performed",
    )
    ai_flags: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True,
        comment="List of AI-detected flags/warnings",
    )

    # -------------------------------------------------------------------------
    # Risk Assessment
    # -------------------------------------------------------------------------
    risk_level: Mapped[Optional[RiskLevel]] = mapped_column(
        Enum(RiskLevel, name="risk_level_enum", create_type=False,
             values_callable=lambda obj: [e.value for e in obj]),
        nullable=True,
        comment="Overall risk classification",
    )
    risk_factors: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True,
        comment="List of identified risk factors",
    )
    pep_check_result: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
        comment="Politically Exposed Person check result (True=is PEP)",
    )
    sanctions_check_result: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
        comment="Sanctions list check result (True=match found)",
    )
    adverse_media_check_result: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
        comment="Adverse media check result (True=found)",
    )

    # -------------------------------------------------------------------------
    # Review Notes
    # -------------------------------------------------------------------------
    reviewer_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Notes from the human reviewer",
    )
    rejection_reasons: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True,
        comment="Structured list of rejection reasons",
    )
    additional_info_requested: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Additional information requested from the applicant",
    )

    # -------------------------------------------------------------------------
    # Processing Metadata
    # -------------------------------------------------------------------------
    celery_task_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Celery task ID for async processing",
    )
    processing_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of processing attempts",
    )
    processing_error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Last processing error message",
    )
    langgraph_state: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="LangGraph agent state snapshot",
    )

    # -------------------------------------------------------------------------
    # Timestamps
    # -------------------------------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Submission creation timestamp",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Last update timestamp",
    )

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    user: Mapped["User"] = relationship(
        "User",
        back_populates="kyc_submissions",
        foreign_keys=[user_id],
        lazy="selectin",
    )

    reviewer: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="reviewed_submissions",
        foreign_keys=[reviewer_id],
        lazy="selectin",
    )

    documents: Mapped[List["Document"]] = relationship(
        "Document",
        back_populates="kyc_submission",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    audit_logs: Mapped[List["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="kyc_submission",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    workflow_steps: Mapped[List["KYCWorkflowStep"]] = relationship(
        "KYCWorkflowStep",
        back_populates="kyc_submission",
        cascade="all, delete-orphan",
        order_by="KYCWorkflowStep.step_order",
        lazy="selectin",
    )

    final_report: Mapped[Optional["KYCFinalReport"]] = relationship(
        "KYCFinalReport",
        back_populates="kyc_submission",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="selectin",
    )

    admin_decisions: Mapped[List["KYCAdminDecision"]] = relationship(
        "KYCAdminDecision",
        back_populates="kyc_submission",
        cascade="all, delete-orphan",
        order_by="KYCAdminDecision.decided_at.desc()",
        lazy="selectin",
    )

    timeline_events: Mapped[List["KYCTimeline"]] = relationship(
        "KYCTimeline",
        back_populates="kyc_submission",
        cascade="all, delete-orphan",
        order_by="KYCTimeline.occurred_at",
        lazy="selectin",
    )

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------

    @property
    def is_terminal(self) -> bool:
        """Check if the submission has reached a terminal state."""
        return self.status in (
            KYCStatus.APPROVED,
            KYCStatus.REJECTED,
            KYCStatus.EXPIRED,
            KYCStatus.CANCELLED,
        )

    @property
    def is_approved(self) -> bool:
        """Check if KYC is approved."""
        return self.status == KYCStatus.APPROVED

    @property
    def needs_review(self) -> bool:
        """Check if submission requires manual review."""
        return self.status == KYCStatus.UNDER_REVIEW

    @property
    def applicant_full_name(self) -> str:
        """Get the applicant's full name."""
        return f"{self.applicant_first_name} {self.applicant_last_name}".strip()

    def __repr__(self) -> str:
        return (
            f"<KYCSubmission id={self.id} "
            f"ref={self.reference_number} "
            f"status={self.status}>"
        )
