"""
KYC Workflow Models

SQLAlchemy ORM models for the extended admin review workflow:
  - KYCWorkflowStep   : per-agent execution record with status/summary
  - KYCFinalReport    : generated KYC report stored after final report agent
  - KYCAdminDecision  : admin approve/reject/manual-review actions
  - KYCTimeline       : ordered audit trail / journey log for a case
"""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

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
    func,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.kyc import KYCSubmission
    from app.models.user import User


# =============================================================================
# Enumerations
# =============================================================================


class WorkflowStepName(str, enum.Enum):
    """Ordered workflow step names matching the LangGraph pipeline."""
    INGESTION = "ingestion"
    DOCUMENT_PROCESSING = "document_processing"
    CUSTOMER_DOCUMENT_ANALYSIS = "customer_document_analysis"
    CUSTOMER_COMPLIANCE_REVIEW = "customer_compliance_review"
    GOVERNMENT_IDENTITY_VALIDATION = "government_identity_validation"
    IDENTITY_VERIFICATION = "identity_verification"
    FINAL_REPORT_GENERATION = "final_report_generation"
    DECISION = "decision"


class WorkflowStepStatus(str, enum.Enum):
    """Execution status of a single workflow step."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class AdminDecisionType(str, enum.Enum):
    """Type of admin decision."""
    APPROVED = "approved"
    REJECTED = "rejected"
    MANUAL_REVIEW = "manual_review"


# =============================================================================
# KYCWorkflowStep
# =============================================================================


class KYCWorkflowStep(Base):
    """
    Records the execution state of a single agent step within a KYC review.

    One record exists per (submission, step_name) pair. Updated in-place
    as the agent progresses through pending → in_progress → completed/failed.
    """

    __tablename__ = "kyc_workflow_steps"

    __table_args__ = (
        Index("ix_wfstep_submission_id", "submission_id"),
        Index("ix_wfstep_step_name", "step_name"),
        Index("ix_wfstep_status", "status"),
        {"schema": None},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    submission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("kyc_submissions.id", ondelete="CASCADE"),
        nullable=False,
    )

    step_name: Mapped[WorkflowStepName] = mapped_column(
        Enum(WorkflowStepName,
             name="workflow_step_name_enum",
             create_type=False,
             values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )

    step_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Display order (0-based)",
    )

    status: Mapped[WorkflowStepStatus] = mapped_column(
        Enum(WorkflowStepStatus,
             name="workflow_step_status_enum",
             create_type=False,
             values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=WorkflowStepStatus.PENDING,
    )

    summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="One-line human-readable outcome summary",
    )

    details: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Structured output fields from the agent",
    )

    score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Primary numeric score produced by this step (0.0-1.0)",
    )

    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Error description if the step failed",
    )

    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    duration_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Step execution duration in milliseconds",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    kyc_submission: Mapped["KYCSubmission"] = relationship(
        "KYCSubmission",
        back_populates="workflow_steps",
        foreign_keys=[submission_id],
    )

    def __repr__(self) -> str:
        return (
            f"<KYCWorkflowStep submission={self.submission_id} "
            f"step={self.step_name} status={self.status}>"
        )


# =============================================================================
# KYCFinalReport
# =============================================================================


class KYCFinalReport(Base):
    """
    Stores the structured KYC report generated by the Final Report agent.

    One report per submission (unique constraint enforced).
    Admins retrieve this to make their approve/reject/manual-review decision.
    """

    __tablename__ = "kyc_final_reports"

    __table_args__ = (
        Index("ix_finalreport_submission_id", "submission_id", unique=True),
        {"schema": None},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    submission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("kyc_submissions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # Report content
    report_data: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Full structured report from the Final Report agent",
    )

    # Scores and recommendation
    final_confidence_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )

    recommended_action: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="approve | reject | manual_review",
    )

    fraud_detected: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    compliance_passed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    government_validated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    identity_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Document quality flags
    document_quality_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    document_tampered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    generated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    kyc_submission: Mapped["KYCSubmission"] = relationship(
        "KYCSubmission",
        back_populates="final_report",
        foreign_keys=[submission_id],
    )

    def __repr__(self) -> str:
        return (
            f"<KYCFinalReport submission={self.submission_id} "
            f"recommendation={self.recommended_action}>"
        )


# =============================================================================
# KYCAdminDecision
# =============================================================================


class KYCAdminDecision(Base):
    """
    Records explicit admin decisions (approve/reject/manual-review) on a case.

    Multiple decisions can exist per case (audit trail of all admin actions).
    The most recent active decision is the effective one.
    """

    __tablename__ = "kyc_admin_decisions"

    __table_args__ = (
        Index("ix_admindecision_submission_id", "submission_id"),
        Index("ix_admindecision_admin_id", "admin_id"),
        {"schema": None},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    submission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("kyc_submissions.id", ondelete="CASCADE"),
        nullable=False,
    )

    admin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    decision_type: Mapped[AdminDecisionType] = mapped_column(
        Enum(AdminDecisionType,
             name="admin_decision_type_enum",
             create_type=False,
             values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )

    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Admin notes / reason for the decision",
    )

    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    kyc_submission: Mapped["KYCSubmission"] = relationship(
        "KYCSubmission",
        back_populates="admin_decisions",
        foreign_keys=[submission_id],
    )

    admin: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[admin_id],
    )

    def __repr__(self) -> str:
        return (
            f"<KYCAdminDecision submission={self.submission_id} "
            f"type={self.decision_type}>"
        )


# =============================================================================
# KYCTimeline
# =============================================================================


class KYCTimeline(Base):
    """
    Chronological event log for a KYC case.

    Every significant event (workflow step start/complete, admin action,
    status change) is recorded here. Used to render the journey log in the UI.
    """

    __tablename__ = "kyc_timeline"

    __table_args__ = (
        Index("ix_timeline_submission_id", "submission_id"),
        Index("ix_timeline_occurred_at", "occurred_at"),
        {"schema": None},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    submission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("kyc_submissions.id", ondelete="CASCADE"),
        nullable=False,
    )

    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment=(
            "Event category: WORKFLOW_STARTED, STEP_STARTED, STEP_COMPLETED, "
            "STEP_FAILED, ADMIN_DECISION, STATUS_CHANGED, REPORT_GENERATED"
        ),
    )

    event_title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Short display title for the timeline entry",
    )

    event_detail: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Longer description or agent message",
    )

    actor: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Who/what triggered this event (agent name or admin username)",
    )

    event_metadata: Mapped[Optional[dict]] = mapped_column(
        "metadata",  # DB column name kept as 'metadata'; 'metadata' is reserved in SQLAlchemy Declarative
        JSON,
        nullable=True,
        comment="Additional structured data for this event",
    )

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    kyc_submission: Mapped["KYCSubmission"] = relationship(
        "KYCSubmission",
        back_populates="timeline_events",
        foreign_keys=[submission_id],
    )

    def __repr__(self) -> str:
        return (
            f"<KYCTimeline submission={self.submission_id} "
            f"event={self.event_type} at={self.occurred_at}>"
        )
