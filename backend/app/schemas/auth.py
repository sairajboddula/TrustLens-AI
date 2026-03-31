"""
KYC Application - Authentication Schemas

Pydantic schemas for authentication request/response validation.
Includes login, token management, and password reset flows.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


# =============================================================================
# Login / Token Schemas
# =============================================================================

class LoginRequest(BaseModel):
    """Schema for user login request."""

    email: str = Field(
        ...,
        description="User's email address",
        examples=["user@example.com"],
    )
    password: str = Field(
        ...,
        description="User's password",
        min_length=1,
        examples=["SecurePassword123!"],
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "email": "user@example.com",
                "password": "SecurePassword123!",
            }
        }
    }


class TokenResponse(BaseModel):
    """Schema for successful authentication token response."""

    access_token: str = Field(
        ...,
        description="JWT access token for API authentication",
    )
    refresh_token: str = Field(
        ...,
        description="JWT refresh token for obtaining new access tokens",
    )
    token_type: str = Field(
        default="bearer",
        description="Token type (always 'bearer')",
    )
    expires_in: int = Field(
        ...,
        description="Access token expiry time in seconds",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 1800,
            }
        }
    }


class TokenRefreshRequest(BaseModel):
    """Schema for token refresh request."""

    refresh_token: str = Field(
        ...,
        description="Valid refresh token",
    )


class TokenPayload(BaseModel):
    """Schema representing the decoded JWT token payload."""

    sub: str = Field(..., description="Subject (user ID)")
    exp: datetime = Field(..., description="Expiry timestamp")
    iat: datetime = Field(..., description="Issued-at timestamp")
    type: str = Field(..., description="Token type (access/refresh)")
    jti: str = Field(..., description="JWT ID for revocation")
    role: Optional[str] = Field(None, description="User role")
    email: Optional[str] = Field(None, description="User email")


class LogoutResponse(BaseModel):
    """Schema for logout response."""

    message: str = Field(
        default="Successfully logged out",
        description="Logout confirmation message",
    )


# =============================================================================
# Password Management Schemas
# =============================================================================

class PasswordChangeRequest(BaseModel):
    """Schema for changing an authenticated user's password."""

    current_password: str = Field(
        ...,
        description="Current password for verification",
        min_length=1,
    )
    new_password: str = Field(
        ...,
        description="New password (must meet strength requirements)",
        min_length=8,
        max_length=128,
    )
    confirm_new_password: str = Field(
        ...,
        description="Confirmation of new password (must match new_password)",
    )

    @field_validator("confirm_new_password")
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        """Validate that new_password and confirm_new_password match."""
        if "new_password" in info.data and v != info.data["new_password"]:
            raise ValueError("Passwords do not match")
        return v

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate new password meets strength requirements."""
        errors = []
        if not any(c.isupper() for c in v):
            errors.append("must contain uppercase letter")
        if not any(c.islower() for c in v):
            errors.append("must contain lowercase letter")
        if not any(c.isdigit() for c in v):
            errors.append("must contain digit")
        special = set("!@#$%^&*()_+-=[]{}|;:,.<>?")
        if not any(c in special for c in v):
            errors.append("must contain special character")
        if errors:
            raise ValueError(f"Password {', '.join(errors)}")
        return v


class PasswordResetRequest(BaseModel):
    """Schema for initiating a password reset (forgot password)."""

    email: EmailStr = Field(
        ...,
        description="Email address associated with the account",
        examples=["user@example.com"],
    )


class PasswordResetConfirm(BaseModel):
    """Schema for confirming a password reset with token."""

    token: str = Field(
        ...,
        description="Password reset token from email",
        min_length=1,
    )
    new_password: str = Field(
        ...,
        description="New password",
        min_length=8,
        max_length=128,
    )
    confirm_new_password: str = Field(
        ...,
        description="Confirmation of new password",
    )

    @field_validator("confirm_new_password")
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        """Validate passwords match."""
        if "new_password" in info.data and v != info.data["new_password"]:
            raise ValueError("Passwords do not match")
        return v

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password strength."""
        errors = []
        if not any(c.isupper() for c in v):
            errors.append("must contain uppercase letter")
        if not any(c.islower() for c in v):
            errors.append("must contain lowercase letter")
        if not any(c.isdigit() for c in v):
            errors.append("must contain digit")
        special = set("!@#$%^&*()_+-=[]{}|;:,.<>?")
        if not any(c in special for c in v):
            errors.append("must contain special character")
        if errors:
            raise ValueError(f"Password {', '.join(errors)}")
        return v


class PasswordResetResponse(BaseModel):
    """Schema for password reset initiation response."""

    message: str = Field(
        ...,
        description="User-facing message",
    )


# =============================================================================
# Email Verification Schemas
# =============================================================================

class EmailVerificationRequest(BaseModel):
    """Schema for verifying email with token."""

    token: str = Field(
        ...,
        description="Email verification token",
        min_length=1,
    )


class EmailVerificationResponse(BaseModel):
    """Schema for email verification response."""

    message: str = Field(..., description="Verification result message")
    verified: bool = Field(..., description="Whether verification succeeded")
