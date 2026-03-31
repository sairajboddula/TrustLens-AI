"""
KYC Application - Document Model

SQLAlchemy ORM model for identity documents uploaded as part of
KYC submissions. Tracks file metadata, OCR results, and verification state.
"""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    BigInteger,
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


# =============================================================================
# Enumerations
# =============================================================================

class DocumentType(str, enum.Enum):
    """Classification of document types."""
    PASSPORT = "passport"
    NATIONAL_ID_FRONT = "national_id_front"
    NATIONAL_ID_BACK = "national_id_back"
    DRIVERS_LICENSE_FRONT = "drivers_license_front"
    DRIVERS_LICENSE_BACK = "drivers_license_back"
    RESIDENCE_PERMIT = "residence_permit"
    UTILITY_BILL = "utility_bill"
    BANK_STATEMENT = "bank_statement"
    TAX_DOCUMENT = "tax_document"
    SELFIE_PHOTO = "selfie_photo"
    SELFIE_WITH_DOCUMENT = "selfie_with_document"
    OTHER = "other"


class DocumentStatus(str, enum.Enum):
    """Document processing status."""
    PENDING = "pending"           # Uploaded, awaiting processing
    PROCESSING = "processing"     # OCR/AI processing in progress
    PROCESSED = "processed"       # Processing completed successfully
    VERIFIED = "verified"         # Document verified as authentic
    REJECTED = "rejected"         # Document rejected (tampered/expired/etc.)
    ERROR = "error"               # Processing failed with error


# =============================================================================
# Document Model
# =============================================================================

class Document(Base):
    """
    Identity document model.

    Represents a file uploaded by a user as part of their KYC submission.
    Stores the file metadata, storage path, OCR results, and AI analysis.
    """

    __tablename__ = "documents"

    __table_args__ = (
        Index("ix_documents_kyc_submission_id", "kyc_submission_id"),
        Index("ix_documents_document_type", "document_type"),
        Index("ix_documents_status", "status"),
        Index("ix_documents_created_at", "created_at"),
        {"schema": None},
    )

    # -------------------------------------------------------------------------
    # Primary Key
    # -------------------------------------------------------------------------
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique document identifier (UUID v4)",
    )

    # -------------------------------------------------------------------------
    # Foreign Keys
    # -------------------------------------------------------------------------
    kyc_submission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("kyc_submissions.id", ondelete="CASCADE"),
        nullable=False,
        comment="Associated KYC submission ID",
    )

    # -------------------------------------------------------------------------
    # Document Classification
    # -------------------------------------------------------------------------
    document_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType, name="document_type_enum", create_type=False,
             values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        comment="Type of identity document",
    )
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status_enum", create_type=False,
             values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=DocumentStatus.PENDING,
        comment="Processing status",
    )

    # -------------------------------------------------------------------------
    # File Metadata
    # -------------------------------------------------------------------------
    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Original filename as uploaded by user",
    )
    stored_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Stored filename (UUID-based, prevents collisions)",
    )
    storage_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Full storage path or object storage key",
    )
    file_size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="File size in bytes",
    )
    mime_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="MIME type of the file",
    )
    file_hash_sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="SHA-256 hash of file contents for integrity verification",
    )
    is_encrypted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether the stored file is encrypted at rest",
    )

    # -------------------------------------------------------------------------
    # Image Metadata (for image files)
    # -------------------------------------------------------------------------
    image_width: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Image width in pixels",
    )
    image_height: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Image height in pixels",
    )
    image_dpi: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Image resolution in DPI",
    )

    # -------------------------------------------------------------------------
    # OCR Results
    # -------------------------------------------------------------------------
    ocr_raw_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Raw text extracted by OCR",
    )
    ocr_structured_data: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Structured data parsed from OCR output",
    )
    ocr_confidence: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="OCR confidence score (0.0-1.0)",
    )
    ocr_language_detected: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        comment="Language detected during OCR",
    )
    ocr_processing_time_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="OCR processing time in milliseconds",
    )

    # -------------------------------------------------------------------------
    # AI Verification Results
    # -------------------------------------------------------------------------
    ai_authenticity_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="AI document authenticity score (0.0-1.0)",
    )
    ai_tamper_detected: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
        comment="Whether AI detected tampering",
    )
    ai_document_expired: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
        comment="Whether the document appears to be expired",
    )
    ai_verification_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="AI-generated verification notes",
    )
    ai_extracted_fields: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Key fields extracted by AI (name, DOB, document number, etc.)",
    )
    ai_analysis_metadata: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Full AI analysis metadata including model used, version, etc.",
    )

    # -------------------------------------------------------------------------
    # Processing Metadata
    # -------------------------------------------------------------------------
    processing_error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if processing failed",
    )
    processing_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of processing attempts",
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When processing was completed",
    )

    # -------------------------------------------------------------------------
    # Timestamps
    # -------------------------------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Document upload timestamp",
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
        comment="Soft deletion timestamp",
    )

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    kyc_submission: Mapped["KYCSubmission"] = relationship(
        "KYCSubmission",
        back_populates="documents",
        lazy="selectin",
    )

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------

    @property
    def is_image(self) -> bool:
        """Check if the document is an image file."""
        return self.mime_type.startswith("image/")

    @property
    def is_pdf(self) -> bool:
        """Check if the document is a PDF."""
        return self.mime_type == "application/pdf"

    @property
    def file_size_mb(self) -> float:
        """Get file size in megabytes."""
        return round(self.file_size_bytes / (1024 * 1024), 2)

    @property
    def is_processed(self) -> bool:
        """Check if document has been processed."""
        return self.status in (
            DocumentStatus.PROCESSED,
            DocumentStatus.VERIFIED,
            DocumentStatus.REJECTED,
        )

    def __repr__(self) -> str:
        return (
            f"<Document id={self.id} "
            f"type={self.document_type} "
            f"status={self.status}>"
        )
