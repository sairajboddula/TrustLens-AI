"""
KYC Application - User Model

SQLAlchemy ORM model representing application users with roles,
authentication state, and profile information.
"""

import enum
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.kyc import KYCSubmission
    from app.models.audit_log import AuditLog


# =============================================================================
# Enumerations
# =============================================================================

class UserRole(str, enum.Enum):
    """User role enumeration for RBAC."""
    ADMIN = "admin"           # Full system access
    REVIEWER = "reviewer"     # Can review and approve/reject KYC
    CUSTOMER = "customer"     # Can submit KYC applications
    ANALYST = "analyst"       # Read-only access for reporting


class UserStatus(str, enum.Enum):
    """User account status."""
    ACTIVE = "active"           # Account is active
    INACTIVE = "inactive"       # Account is deactivated
    SUSPENDED = "suspended"     # Account suspended due to policy violation
    PENDING_VERIFY = "pending_verify"  # Email not yet verified
    LOCKED = "locked"           # Account locked after too many failed attempts


# =============================================================================
# User Model
# =============================================================================

class User(Base):
    """
    User account model.

    Represents an authenticated user with role-based access control.
    Passwords are stored as bcrypt hashes; plain-text passwords are
    never persisted.
    """

    __tablename__ = "users"

    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        UniqueConstraint("username", name="uq_users_username"),
        Index("ix_users_email", "email"),
        Index("ix_users_username", "username"),
        Index("ix_users_role", "role"),
        Index("ix_users_status", "status"),
        Index("ix_users_created_at", "created_at"),
        {"schema": None},
    )

    # -------------------------------------------------------------------------
    # Primary Key
    # -------------------------------------------------------------------------
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique user identifier (UUID v4)",
    )

    # -------------------------------------------------------------------------
    # Identity Fields
    # -------------------------------------------------------------------------
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="User email address (unique, used for login)",
    )
    username: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Unique display username",
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Bcrypt hashed password",
    )

    # -------------------------------------------------------------------------
    # Profile Fields
    # -------------------------------------------------------------------------
    first_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="User's first name",
    )
    last_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="User's last name",
    )
    phone_number: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="User's phone number in E.164 format",
    )
    date_of_birth: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="User's date of birth",
    )
    nationality: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="User's nationality (country name or ISO 3166-1 alpha-3 code)",
    )
    address_line1: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Address line 1",
    )
    address_line2: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Address line 2",
    )
    city: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="City",
    )
    state_province: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="State or province",
    )
    postal_code: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Postal/ZIP code",
    )
    country: Mapped[Optional[str]] = mapped_column(
        String(3),
        nullable=True,
        comment="Country as ISO 3166-1 alpha-3 code",
    )

    # -------------------------------------------------------------------------
    # Role & Status
    # -------------------------------------------------------------------------
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role_enum", create_type=False,
             values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=UserRole.CUSTOMER,
        comment="User's RBAC role",
    )
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status_enum", create_type=False,
             values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=UserStatus.PENDING_VERIFY,
        comment="Account status",
    )

    # -------------------------------------------------------------------------
    # Authentication State
    # -------------------------------------------------------------------------
    is_email_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether email has been verified",
    )
    email_verification_token: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Email verification token (cleared after verification)",
    )
    password_reset_token: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Password reset token (time-limited)",
    )
    password_reset_expires: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Password reset token expiry time",
    )
    failed_login_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Consecutive failed login attempts (resets on success)",
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp of last successful login",
    )
    last_login_ip: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
        comment="IP address of last login (supports IPv6)",
    )

    # -------------------------------------------------------------------------
    # Timestamps
    # -------------------------------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Account creation timestamp",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Last update timestamp",
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Soft deletion timestamp (NULL = not deleted)",
    )

    # -------------------------------------------------------------------------
    # Additional Metadata
    # -------------------------------------------------------------------------
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Internal notes about this user (admin use)",
    )

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    kyc_submissions: Mapped[List["KYCSubmission"]] = relationship(
        "KYCSubmission",
        back_populates="user",
        foreign_keys="KYCSubmission.user_id",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    reviewed_submissions: Mapped[List["KYCSubmission"]] = relationship(
        "KYCSubmission",
        back_populates="reviewer",
        foreign_keys="KYCSubmission.reviewer_id",
        lazy="selectin",
    )

    audit_logs: Mapped[List["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------

    @property
    def full_name(self) -> str:
        """Return the user's full name."""
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def is_active(self) -> bool:
        """Check if the user account is active."""
        return self.status == UserStatus.ACTIVE and self.deleted_at is None

    @property
    def is_admin(self) -> bool:
        """Check if the user has admin role."""
        return self.role == UserRole.ADMIN

    @property
    def is_reviewer(self) -> bool:
        """Check if the user can review KYC submissions."""
        return self.role in (UserRole.ADMIN, UserRole.REVIEWER)

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} role={self.role}>"
