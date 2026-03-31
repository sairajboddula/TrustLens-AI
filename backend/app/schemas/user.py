"""
KYC Application - User Schemas

Pydantic schemas for user creation, updates, and API responses.
Handles password validation, profile data, and role management.
"""

import re
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.models.user import UserRole, UserStatus


# =============================================================================
# Base Schema
# =============================================================================

class UserBase(BaseModel):
    """Base schema with common user fields."""

    email: EmailStr = Field(
        ...,
        description="User's email address (unique)",
        examples=["john.doe@example.com"],
    )
    username: str = Field(
        ...,
        description="Unique display username",
        min_length=3,
        max_length=100,
        examples=["johndoe"],
    )
    first_name: str = Field(
        ...,
        description="First name",
        min_length=1,
        max_length=100,
        examples=["John"],
    )
    last_name: str = Field(
        ...,
        description="Last name",
        min_length=1,
        max_length=100,
        examples=["Doe"],
    )

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Validate username format (alphanumeric + underscores/hyphens)."""
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError(
                "Username may only contain letters, numbers, underscores, and hyphens"
            )
        return v.lower()

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate name contains only valid characters."""
        if not re.match(r"^[a-zA-Z\s\-'\.]+$", v):
            raise ValueError("Name contains invalid characters")
        return v.strip()


# =============================================================================
# Create Schema
# =============================================================================

class UserCreate(UserBase):
    """Schema for creating a new user account."""

    password: str = Field(
        ...,
        description="Password (min 8 chars, must include upper, lower, digit, special)",
        min_length=8,
        max_length=128,
        examples=["SecurePassword123!"],
    )
    confirm_password: str = Field(
        ...,
        description="Password confirmation (must match password)",
    )
    phone_number: Optional[str] = Field(
        default=None,
        description="Phone number in E.164 format (e.g., +1234567890)",
        examples=["+12345678901"],
    )
    date_of_birth: Optional[datetime] = Field(
        default=None,
        description="Date of birth (must be 18+ years old)",
    )
    nationality: Optional[str] = Field(
        default=None,
        description="Nationality as ISO 3166-1 alpha-3 country code",
        min_length=3,
        max_length=3,
        examples=["USA"],
    )

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        """Ensure confirm_password matches password."""
        if "password" in info.data and v != info.data["password"]:
            raise ValueError("Passwords do not match")
        return v

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Enforce strong password requirements."""
        errors = []
        if not any(c.isupper() for c in v):
            errors.append("must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            errors.append("must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            errors.append("must contain at least one digit")
        special = set("!@#$%^&*()_+-=[]{}|;:,.<>?")
        if not any(c in special for c in v):
            errors.append("must contain at least one special character")
        if errors:
            raise ValueError(f"Password {'; '.join(errors)}")
        return v

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        """Validate E.164 phone number format."""
        if v is None:
            return v
        if not re.match(r"^\+[1-9]\d{7,14}$", v):
            raise ValueError("Phone number must be in E.164 format (e.g., +12345678901)")
        return v

    @field_validator("nationality")
    @classmethod
    def validate_nationality(cls, v: Optional[str]) -> Optional[str]:
        """Validate ISO 3166-1 alpha-3 country code (uppercase)."""
        if v is None:
            return v
        if not re.match(r"^[A-Z]{3}$", v.upper()):
            raise ValueError("Nationality must be a valid ISO 3166-1 alpha-3 code (e.g., 'USA')")
        return v.upper()

    model_config = {
        "json_schema_extra": {
            "example": {
                "email": "john.doe@example.com",
                "username": "johndoe",
                "first_name": "John",
                "last_name": "Doe",
                "password": "SecurePass123!",
                "confirm_password": "SecurePass123!",
                "phone_number": "+12345678901",
                "nationality": "USA",
            }
        }
    }


# =============================================================================
# Update Schemas
# =============================================================================

class UserUpdate(BaseModel):
    """Schema for users updating their own profile."""

    first_name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
    )
    last_name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
    )
    phone_number: Optional[str] = Field(default=None)
    date_of_birth: Optional[datetime] = Field(default=None)
    nationality: Optional[str] = Field(default=None, min_length=3, max_length=3)
    address_line1: Optional[str] = Field(default=None, max_length=255)
    address_line2: Optional[str] = Field(default=None, max_length=255)
    city: Optional[str] = Field(default=None, max_length=100)
    state_province: Optional[str] = Field(default=None, max_length=100)
    postal_code: Optional[str] = Field(default=None, max_length=20)
    country: Optional[str] = Field(default=None, min_length=3, max_length=3)

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not re.match(r"^\+[1-9]\d{7,14}$", v):
            raise ValueError("Phone number must be in E.164 format")
        return v

    @field_validator("nationality", "country")
    @classmethod
    def validate_country_code(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not re.match(r"^[A-Z]{3}$", v.upper()):
            raise ValueError("Must be a valid ISO 3166-1 alpha-3 code")
        return v.upper()


class UserAdminUpdate(BaseModel):
    """Schema for admins updating any user's account."""

    role: Optional[UserRole] = Field(default=None)
    status: Optional[UserStatus] = Field(default=None)
    is_email_verified: Optional[bool] = Field(default=None)
    notes: Optional[str] = Field(default=None, max_length=2000)


# =============================================================================
# Response Schemas
# =============================================================================

class UserResponse(BaseModel):
    """Schema for user data in API responses."""

    id: UUID
    email: str
    username: str
    first_name: str
    last_name: str
    full_name: str
    phone_number: Optional[str]
    date_of_birth: Optional[datetime]
    nationality: Optional[str]
    address_line1: Optional[str]
    address_line2: Optional[str]
    city: Optional[str]
    state_province: Optional[str]
    postal_code: Optional[str]
    country: Optional[str]
    role: UserRole
    status: UserStatus
    is_email_verified: bool
    last_login_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_model(cls, user) -> "UserResponse":
        """Create UserResponse from User ORM model."""
        data = {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "full_name": user.full_name,
            "phone_number": user.phone_number,
            "date_of_birth": user.date_of_birth,
            "nationality": user.nationality,
            "address_line1": user.address_line1,
            "address_line2": user.address_line2,
            "city": user.city,
            "state_province": user.state_province,
            "postal_code": user.postal_code,
            "country": user.country,
            "role": user.role,
            "status": user.status,
            "is_email_verified": user.is_email_verified,
            "last_login_at": user.last_login_at,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
        }
        return cls(**data)


class UserListResponse(BaseModel):
    """Schema for paginated user list responses."""

    items: List[UserResponse]
    total: int
    page: int
    size: int
    pages: int

    model_config = {"from_attributes": True}


class UserSummary(BaseModel):
    """Minimal user summary for embedding in other responses."""

    id: UUID
    email: str
    username: str
    full_name: str
    role: UserRole

    model_config = {"from_attributes": True}
