"""
KYC Application - Document Schemas

Pydantic schemas for document upload, processing, and API responses.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.document import DocumentStatus, DocumentType


# =============================================================================
# Base Schema
# =============================================================================

class DocumentBase(BaseModel):
    """Base document schema with common fields."""

    document_type: DocumentType = Field(
        ...,
        description="Type of identity document",
    )


# =============================================================================
# Response Schemas
# =============================================================================

class OCRResult(BaseModel):
    """Embedded OCR result schema."""

    raw_text: Optional[str] = None
    structured_data: Optional[Dict[str, Any]] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    language_detected: Optional[str] = None
    processing_time_ms: Optional[int] = None


class AIDocumentAnalysis(BaseModel):
    """Embedded AI document analysis schema."""

    authenticity_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    tamper_detected: Optional[bool] = None
    document_expired: Optional[bool] = None
    verification_notes: Optional[str] = None
    extracted_fields: Optional[Dict[str, Any]] = None


class DocumentResponse(BaseModel):
    """Full document response schema."""

    id: UUID
    kyc_submission_id: UUID
    document_type: DocumentType
    status: DocumentStatus
    original_filename: str
    file_size_bytes: int
    file_size_mb: float
    mime_type: str
    is_image: bool
    is_pdf: bool

    # Image metadata
    image_width: Optional[int]
    image_height: Optional[int]
    image_dpi: Optional[int]

    # OCR results
    ocr_result: Optional[OCRResult] = None

    # AI analysis
    ai_analysis: Optional[AIDocumentAnalysis] = None

    # Processing metadata
    processing_attempts: int
    processing_error: Optional[str]
    processed_at: Optional[datetime]

    # Timestamps
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_model(cls, document) -> "DocumentResponse":
        """Create DocumentResponse from Document ORM model."""

        ocr_result = None
        if document.ocr_raw_text is not None or document.ocr_structured_data is not None:
            ocr_result = OCRResult(
                raw_text=document.ocr_raw_text,
                structured_data=document.ocr_structured_data,
                confidence=document.ocr_confidence,
                language_detected=document.ocr_language_detected,
                processing_time_ms=document.ocr_processing_time_ms,
            )

        ai_analysis = None
        if document.ai_authenticity_score is not None:
            ai_analysis = AIDocumentAnalysis(
                authenticity_score=document.ai_authenticity_score,
                tamper_detected=document.ai_tamper_detected,
                document_expired=document.ai_document_expired,
                verification_notes=document.ai_verification_notes,
                extracted_fields=document.ai_extracted_fields,
            )

        return cls(
            id=document.id,
            kyc_submission_id=document.kyc_submission_id,
            document_type=document.document_type,
            status=document.status,
            original_filename=document.original_filename,
            file_size_bytes=document.file_size_bytes,
            file_size_mb=document.file_size_mb,
            mime_type=document.mime_type,
            is_image=document.is_image,
            is_pdf=document.is_pdf,
            image_width=document.image_width,
            image_height=document.image_height,
            image_dpi=document.image_dpi,
            ocr_result=ocr_result,
            ai_analysis=ai_analysis,
            processing_attempts=document.processing_attempts,
            processing_error=document.processing_error,
            processed_at=document.processed_at,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )


class DocumentSummary(BaseModel):
    """Minimal document summary for list views."""

    id: UUID
    document_type: DocumentType
    status: DocumentStatus
    original_filename: str
    file_size_mb: float
    mime_type: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    """Schema for paginated document list responses."""

    items: List[DocumentSummary]
    total: int
    page: int
    size: int
    pages: int

    model_config = {"from_attributes": True}


class DocumentUploadResponse(BaseModel):
    """Schema for document upload success response."""

    document_id: UUID = Field(..., description="ID of the uploaded document")
    kyc_submission_id: UUID = Field(..., description="Associated KYC submission ID")
    document_type: DocumentType
    original_filename: str
    file_size_mb: float
    status: DocumentStatus
    message: str = Field(
        default="Document uploaded successfully. Processing will begin shortly.",
        description="Upload status message",
    )
    created_at: datetime

    model_config = {"from_attributes": True}
