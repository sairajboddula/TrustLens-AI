"""
KYC Application - KYC Submission Schemas

Pydantic schemas for KYC submission creation, updates, and API responses.
Handles workflow state transitions and AI verification result serialization.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.kyc import KYCDocumentType, KYCStatus, RiskLevel
from app.schemas.document import DocumentResponse
from app.schemas.user import UserSummary


# =============================================================================
# Create / Submit Schemas
# =============================================================================

class KYCSubmissionCreate(BaseModel):
    """Schema for creating a new KYC submission."""

    applicant_first_name: str = Field(
        ...,
        description="Applicant's first name",
        min_length=1,
        max_length=100,
        examples=["John"],
    )
    applicant_last_name: str = Field(
        ...,
        description="Applicant's last name",
        min_length=1,
        max_length=100,
        examples=["Doe"],
    )
    applicant_date_of_birth: Optional[datetime] = Field(
        default=None,
        description="Applicant's date of birth",
    )
    applicant_nationality: Optional[str] = Field(
        default=None,
        description="Applicant's nationality (country name or ISO 3166-1 alpha-3)",
        max_length=100,
    )
    applicant_address: Optional[str] = Field(
        default=None,
        description="Applicant's full address",
        max_length=500,
    )
    applicant_phone: Optional[str] = Field(
        default=None,
        description="Applicant's phone number",
        max_length=20,
    )
    applicant_email: Optional[str] = Field(
        default=None,
        description="Applicant's email address",
        max_length=255,
    )
    primary_document_type: KYCDocumentType = Field(
        ...,
        description="Type of the primary identity document being submitted",
    )
    primary_document_number: Optional[str] = Field(
        default=None,
        description="Document number / ID number from the primary document",
        max_length=100,
    )
    primary_document_issuing_country: Optional[str] = Field(
        default=None,
        description="Issuing country of primary document (free text or ISO 3166-1 alpha-3)",
        max_length=100,
    )
    primary_document_expiry: Optional[datetime] = Field(
        default=None,
        description="Expiry date of the primary document",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "applicant_first_name": "John",
                "applicant_last_name": "Doe",
                "applicant_date_of_birth": "1990-05-15T00:00:00Z",
                "applicant_nationality": "USA",
                "applicant_address": "123 Main St, New York, NY 10001",
                "applicant_phone": "+12125551234",
                "applicant_email": "john.doe@example.com",
                "primary_document_type": "passport",
            }
        }
    }


# =============================================================================
# Update Schemas
# =============================================================================

class KYCSubmissionUpdate(BaseModel):
    """Schema for updating a draft KYC submission."""

    applicant_first_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    applicant_last_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    applicant_date_of_birth: Optional[datetime] = Field(default=None)
    applicant_nationality: Optional[str] = Field(default=None, min_length=3, max_length=3)
    applicant_address: Optional[str] = Field(default=None, max_length=500)
    applicant_phone: Optional[str] = Field(default=None, max_length=20)
    applicant_email: Optional[str] = Field(default=None, max_length=255)
    primary_document_type: Optional[KYCDocumentType] = Field(default=None)


class KYCStatusUpdate(BaseModel):
    """Schema for admin/reviewer updating KYC status."""

    status: KYCStatus = Field(
        ...,
        description="New status to set",
    )
    reason: Optional[str] = Field(
        default=None,
        description="Reason for status change (required for rejections)",
        max_length=2000,
    )
    reviewer_notes: Optional[str] = Field(
        default=None,
        description="Internal reviewer notes",
        max_length=5000,
    )
    rejection_reasons: Optional[List[str]] = Field(
        default=None,
        description="Structured list of rejection reasons",
    )

    @model_validator(mode="after")
    def validate_rejection_requires_reason(self) -> "KYCStatusUpdate":
        """Require reason when rejecting."""
        if self.status == KYCStatus.REJECTED and not self.reason:
            raise ValueError("A reason is required when rejecting a KYC submission")
        return self


# =============================================================================
# AI Verification Result Schemas
# =============================================================================

class AIVerificationResult(BaseModel):
    """Schema for AI verification results embedded in KYC responses."""

    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    document_authenticity_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    face_match_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    liveness_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    fraud_risk_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    extracted_data: Optional[Dict[str, Any]] = None
    verification_details: Optional[Dict[str, Any]] = None
    flags: Optional[List[str]] = None


class RiskAssessment(BaseModel):
    """Schema for risk assessment data."""

    risk_level: Optional[RiskLevel] = None
    risk_factors: Optional[List[str]] = None
    pep_check_result: Optional[bool] = None
    sanctions_check_result: Optional[bool] = None
    adverse_media_check_result: Optional[bool] = None


# =============================================================================
# Response Schemas
# =============================================================================

class KYCSubmissionResponse(BaseModel):
    """Full KYC submission response schema."""

    id: UUID
    reference_number: str

    # Applicant info
    applicant_first_name: str
    applicant_last_name: str
    applicant_full_name: str
    applicant_date_of_birth: Optional[datetime]
    applicant_nationality: Optional[str]
    applicant_address: Optional[str]
    applicant_phone: Optional[str]
    applicant_email: Optional[str]

    # Document info
    primary_document_type: KYCDocumentType
    primary_document_number: Optional[str]
    primary_document_issuing_country: Optional[str]
    primary_document_expiry: Optional[datetime]

    # Status
    status: KYCStatus
    status_reason: Optional[str]
    submitted_at: Optional[datetime]
    processing_started_at: Optional[datetime]
    processing_completed_at: Optional[datetime]
    reviewed_at: Optional[datetime]
    expires_at: Optional[datetime]

    # AI results
    ai_verification: Optional[AIVerificationResult] = None
    risk_assessment: Optional[RiskAssessment] = None

    # Review
    reviewer_notes: Optional[str]
    rejection_reasons: Optional[List[str]]
    additional_info_requested: Optional[str]

    # Relations
    user: Optional[UserSummary] = None
    reviewer: Optional[UserSummary] = None
    documents: Optional[List[DocumentResponse]] = None

    # Metadata
    processing_attempts: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_model(cls, submission) -> "KYCSubmissionResponse":
        """Create KYCSubmissionResponse from ORM model."""

        # Build AI verification result
        ai_verification = None
        if submission.ai_confidence_score is not None:
            ai_verification = AIVerificationResult(
                confidence_score=submission.ai_confidence_score,
                document_authenticity_score=submission.ai_document_authenticity_score,
                face_match_score=submission.ai_face_match_score,
                liveness_score=submission.ai_liveness_score,
                fraud_risk_score=submission.ai_fraud_risk_score,
                extracted_data=submission.ai_extracted_data,
                verification_details=submission.ai_verification_details,
                flags=submission.ai_flags,
            )

        # Build risk assessment
        risk_assessment = None
        if submission.risk_level is not None:
            risk_assessment = RiskAssessment(
                risk_level=submission.risk_level,
                risk_factors=submission.risk_factors,
                pep_check_result=submission.pep_check_result,
                sanctions_check_result=submission.sanctions_check_result,
                adverse_media_check_result=submission.adverse_media_check_result,
            )

        return cls(
            id=submission.id,
            reference_number=submission.reference_number,
            applicant_first_name=submission.applicant_first_name,
            applicant_last_name=submission.applicant_last_name,
            applicant_full_name=submission.applicant_full_name,
            applicant_date_of_birth=submission.applicant_date_of_birth,
            applicant_nationality=submission.applicant_nationality,
            applicant_address=submission.applicant_address,
            applicant_phone=submission.applicant_phone,
            applicant_email=submission.applicant_email,
            primary_document_type=submission.primary_document_type,
            primary_document_number=submission.primary_document_number,
            primary_document_issuing_country=submission.primary_document_issuing_country,
            primary_document_expiry=submission.primary_document_expiry,
            status=submission.status,
            status_reason=submission.status_reason,
            submitted_at=submission.submitted_at,
            processing_started_at=submission.processing_started_at,
            processing_completed_at=submission.processing_completed_at,
            reviewed_at=submission.reviewed_at,
            expires_at=submission.expires_at,
            ai_verification=ai_verification,
            risk_assessment=risk_assessment,
            reviewer_notes=submission.reviewer_notes,
            rejection_reasons=submission.rejection_reasons,
            additional_info_requested=submission.additional_info_requested,
            user=UserSummary(
                id=submission.user.id,
                email=submission.user.email,
                username=submission.user.username,
                full_name=submission.user.full_name,
                role=submission.user.role,
            ) if submission.user else None,
            reviewer=UserSummary(
                id=submission.reviewer.id,
                email=submission.reviewer.email,
                username=submission.reviewer.username,
                full_name=submission.reviewer.full_name,
                role=submission.reviewer.role,
            ) if submission.reviewer else None,
            documents=[
                DocumentResponse.from_model(doc) for doc in (submission.documents or [])
            ],
            processing_attempts=submission.processing_attempts,
            created_at=submission.created_at,
            updated_at=submission.updated_at,
        )


class KYCSubmissionSummary(BaseModel):
    """Minimal KYC submission summary for list views."""

    id: UUID
    reference_number: str
    applicant_full_name: str
    primary_document_type: KYCDocumentType
    status: KYCStatus
    risk_level: Optional[RiskLevel]
    ai_confidence_score: Optional[float]
    submitted_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class KYCListResponse(BaseModel):
    """Schema for paginated KYC submission list responses."""

    items: List[KYCSubmissionSummary]
    total: int
    page: int
    size: int
    pages: int

    model_config = {"from_attributes": True}


class KYCStatsResponse(BaseModel):
    """Schema for KYC statistics."""

    total_submissions: int
    by_status: Dict[str, int]
    by_risk_level: Dict[str, int]
    auto_approved: int
    auto_rejected: int
    manual_review: int
    avg_processing_time_seconds: Optional[float]
    approval_rate: Optional[float]
