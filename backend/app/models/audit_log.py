"""
KYC Application - Audit Log Model

Immutable audit trail for all significant actions in the system.
Used for compliance, security monitoring, and debugging.
"""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.kyc import KYCSubmission


# =============================================================================
# Enumerations
# =============================================================================

class AuditAction(str, enum.Enum):
    """Types of auditable actions."""

    # User actions
    USER_REGISTERED = "user_registered"
    USER_LOGIN = "user_login"
    USER_LOGIN_FAILED = "user_login_failed"
    USER_LOGOUT = "user_logout"
    USER_UPDATED = "user_updated"
    USER_PASSWORD_CHANGED = "user_password_changed"
    USER_PASSWORD_RESET_REQUESTED = "user_password_reset_requested"
    USER_PASSWORD_RESET = "user_password_reset"
    USER_EMAIL_VERIFIED = "user_email_verified"
    USER_ACTIVATED = "user_activated"
    USER_DEACTIVATED = "user_deactivated"
    USER_SUSPENDED = "user_suspended"
    USER_LOCKED = "user_locked"
    USER_DELETED = "user_deleted"
    USER_ROLE_CHANGED = "user_role_changed"

    # KYC actions
    KYC_CREATED = "kyc_created"
    KYC_SUBMITTED = "kyc_submitted"
    KYC_PROCESSING_STARTED = "kyc_processing_started"
    KYC_PROCESSING_COMPLETED = "kyc_processing_completed"
    KYC_PROCESSING_FAILED = "kyc_processing_failed"
    KYC_UNDER_REVIEW = "kyc_under_review"
    KYC_APPROVED = "kyc_approved"
    KYC_REJECTED = "kyc_rejected"
    KYC_CANCELLED = "kyc_cancelled"
    KYC_EXPIRED = "kyc_expired"
    KYC_RESUBMITTED = "kyc_resubmitted"
    KYC_VIEWED = "kyc_viewed"
    KYC_STATUS_CHANGED = "kyc_status_changed"

    # Document actions
    DOCUMENT_UPLOADED = "document_uploaded"
    DOCUMENT_PROCESSED = "document_processed"
    DOCUMENT_VERIFIED = "document_verified"
    DOCUMENT_REJECTED = "document_rejected"
    DOCUMENT_DOWNLOADED = "document_downloaded"
    DOCUMENT_DELETED = "document_deleted"

    # Admin actions
    ADMIN_USER_LIST_VIEWED = "admin_user_list_viewed"
    ADMIN_KYC_LIST_VIEWED = "admin_kyc_list_viewed"
    ADMIN_STATS_VIEWED = "admin_stats_viewed"
    ADMIN_BULK_ACTION = "admin_bulk_action"

    # System actions
    SYSTEM_STARTUP = "system_startup"
    SYSTEM_SHUTDOWN = "system_shutdown"
    SYSTEM_ERROR = "system_error"


# =============================================================================
# Audit Log Model
# =============================================================================

class AuditLog(Base):
    """
    Immutable audit log entry.

    Records every significant action in the system for compliance,
    security monitoring, and debugging purposes.

    IMPORTANT: Audit log records should NEVER be updated or deleted.
    This table serves as the system of record for all actions.
    """

    __tablename__ = "audit_logs"

    __table_args__ = (
        Index("ix_audit_user_id", "user_id"),
        Index("ix_audit_kyc_submission_id", "kyc_submission_id"),
        Index("ix_audit_action", "action"),
        Index("ix_audit_created_at", "created_at"),
        Index("ix_audit_entity_type", "entity_type"),
        Index("ix_audit_entity_id", "entity_id"),
        Index("ix_audit_ip_address", "ip_address"),
        {"schema": None},
    )

    # -------------------------------------------------------------------------
    # Primary Key
    # -------------------------------------------------------------------------
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique audit log entry ID",
    )

    # -------------------------------------------------------------------------
    # Actor (Who performed the action)
    # -------------------------------------------------------------------------
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="ID of user who performed the action (NULL for system actions)",
    )
    user_email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Email of user at time of action (denormalized for history)",
    )
    user_role: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Role of user at time of action",
    )

    # -------------------------------------------------------------------------
    # Action
    # -------------------------------------------------------------------------
    action: Mapped[AuditAction] = mapped_column(
        Enum(AuditAction, name="audit_action_enum", create_type=False,
             values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        comment="The type of action that was performed",
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Human-readable description of the action",
    )

    # -------------------------------------------------------------------------
    # Entity (What was acted upon)
    # -------------------------------------------------------------------------
    entity_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Type of entity affected (e.g., 'user', 'kyc_submission', 'document')",
    )
    entity_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="ID of the entity affected",
    )
    kyc_submission_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("kyc_submissions.id", ondelete="SET NULL"),
        nullable=True,
        comment="Associated KYC submission (if applicable)",
    )

    # -------------------------------------------------------------------------
    # Context
    # -------------------------------------------------------------------------
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
        comment="Client IP address (supports IPv6)",
    )
    user_agent: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Client user agent string",
    )
    request_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Unique request ID for correlating logs",
    )
    session_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="User session ID",
    )

    # -------------------------------------------------------------------------
    # Change Data
    # -------------------------------------------------------------------------
    old_values: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="State before the action (for update/delete operations)",
    )
    new_values: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="State after the action (for create/update operations)",
    )
    extra_data: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Additional context-specific metadata",
    )

    # -------------------------------------------------------------------------
    # Result
    # -------------------------------------------------------------------------
    success: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
        comment="Whether the action was successful",
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if the action failed",
    )

    # -------------------------------------------------------------------------
    # Timestamp
    # -------------------------------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="When this audit event occurred",
    )

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="audit_logs",
        lazy="selectin",
    )

    kyc_submission: Mapped[Optional["KYCSubmission"]] = relationship(
        "KYCSubmission",
        back_populates="audit_logs",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog id={self.id} "
            f"action={self.action} "
            f"user_id={self.user_id} "
            f"created_at={self.created_at}>"
        )
