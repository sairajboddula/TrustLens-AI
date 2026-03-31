"""
KYC Application - Schemas Package

Pydantic schemas for request/response validation and serialization:
- auth: Login, token, and authentication schemas
- user: User profile and management schemas
- kyc: KYC submission schemas
- document: Document upload and metadata schemas
"""

from app.schemas.auth import (
    LoginRequest,
    TokenResponse,
    TokenRefreshRequest,
    TokenPayload,
    PasswordChangeRequest,
    PasswordResetRequest,
    PasswordResetConfirm,
)
from app.schemas.user import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserListResponse,
    UserAdminUpdate,
)
from app.schemas.kyc import (
    KYCSubmissionCreate,
    KYCSubmissionUpdate,
    KYCSubmissionResponse,
    KYCStatusUpdate,
    KYCListResponse,
)
from app.schemas.document import (
    DocumentResponse,
    DocumentListResponse,
    DocumentUploadResponse,
)

__all__ = [
    # Auth
    "LoginRequest",
    "TokenResponse",
    "TokenRefreshRequest",
    "TokenPayload",
    "PasswordChangeRequest",
    "PasswordResetRequest",
    "PasswordResetConfirm",
    # User
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "UserListResponse",
    "UserAdminUpdate",
    # KYC
    "KYCSubmissionCreate",
    "KYCSubmissionUpdate",
    "KYCSubmissionResponse",
    "KYCStatusUpdate",
    "KYCListResponse",
    # Document
    "DocumentResponse",
    "DocumentListResponse",
    "DocumentUploadResponse",
]
