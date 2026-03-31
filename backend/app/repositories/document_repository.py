"""
KYC Application - Document Repository

Data access layer for Document model operations.
Handles file metadata storage, OCR result persistence,
and AI verification result storage.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, select, update

from app.core.logging_config import get_logger
from app.models.document import Document, DocumentStatus, DocumentType
from app.repositories.base import BaseRepository

logger = get_logger(__name__)


class DocumentRepository(BaseRepository[Document]):
    """
    Repository for Document model database operations.

    Manages document metadata, processing state, OCR results,
    and AI analysis results for identity documents.
    """

    def __init__(self, session):
        super().__init__(Document, session)

    # =========================================================================
    # Creation
    # =========================================================================

    async def create_document(
        self,
        kyc_submission_id: UUID,
        document_type: DocumentType,
        original_filename: str,
        stored_filename: str,
        storage_path: str,
        file_size_bytes: int,
        mime_type: str,
        file_hash_sha256: str,
        image_width: Optional[int] = None,
        image_height: Optional[int] = None,
        image_dpi: Optional[int] = None,
    ) -> Document:
        """
        Create a new document record after file upload.

        Args:
            kyc_submission_id: Associated KYC submission
            document_type: Type of identity document
            original_filename: Original user-provided filename
            stored_filename: Sanitized stored filename (UUID-based)
            storage_path: Full storage path or object key
            file_size_bytes: File size in bytes
            mime_type: MIME type of the uploaded file
            file_hash_sha256: SHA-256 hash for integrity verification
            image_width: Image width in pixels (for images)
            image_height: Image height in pixels (for images)
            image_dpi: Image DPI (for images)

        Returns:
            Newly created Document record
        """
        data = {
            "kyc_submission_id": kyc_submission_id,
            "document_type": document_type,
            "original_filename": original_filename,
            "stored_filename": stored_filename,
            "storage_path": storage_path,
            "file_size_bytes": file_size_bytes,
            "mime_type": mime_type,
            "file_hash_sha256": file_hash_sha256,
            "status": DocumentStatus.PENDING,
            "image_width": image_width,
            "image_height": image_height,
            "image_dpi": image_dpi,
        }

        document = await self.create(data)
        logger.info(
            "Document record created",
            document_id=str(document.id),
            kyc_submission_id=str(kyc_submission_id),
            document_type=document_type,
        )
        return document

    # =========================================================================
    # Status Management
    # =========================================================================

    async def mark_processing(self, document_id: UUID) -> Optional[Document]:
        """Set document status to PROCESSING."""
        return await self.update(
            document_id,
            {"status": DocumentStatus.PROCESSING},
        )

    async def mark_processed(
        self,
        document_id: UUID,
        ocr_raw_text: Optional[str] = None,
        ocr_structured_data: Optional[Dict[str, Any]] = None,
        ocr_confidence: Optional[float] = None,
        ocr_language_detected: Optional[str] = None,
        ocr_processing_time_ms: Optional[int] = None,
        ai_authenticity_score: Optional[float] = None,
        ai_tamper_detected: Optional[bool] = None,
        ai_document_expired: Optional[bool] = None,
        ai_verification_notes: Optional[str] = None,
        ai_extracted_fields: Optional[Dict[str, Any]] = None,
        ai_analysis_metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Document]:
        """
        Store OCR and AI results after successful processing.

        Args:
            document_id: Document to update
            ocr_*: OCR extraction results
            ai_*: AI analysis results

        Returns:
            Updated Document
        """
        now = datetime.now(timezone.utc)

        update_data: Dict[str, Any] = {
            "status": DocumentStatus.PROCESSED,
            "processed_at": now,
        }

        # OCR results
        if ocr_raw_text is not None:
            update_data["ocr_raw_text"] = ocr_raw_text
        if ocr_structured_data is not None:
            update_data["ocr_structured_data"] = ocr_structured_data
        if ocr_confidence is not None:
            update_data["ocr_confidence"] = ocr_confidence
        if ocr_language_detected is not None:
            update_data["ocr_language_detected"] = ocr_language_detected
        if ocr_processing_time_ms is not None:
            update_data["ocr_processing_time_ms"] = ocr_processing_time_ms

        # AI analysis results
        if ai_authenticity_score is not None:
            update_data["ai_authenticity_score"] = ai_authenticity_score
        if ai_tamper_detected is not None:
            update_data["ai_tamper_detected"] = ai_tamper_detected
        if ai_document_expired is not None:
            update_data["ai_document_expired"] = ai_document_expired
        if ai_verification_notes is not None:
            update_data["ai_verification_notes"] = ai_verification_notes
        if ai_extracted_fields is not None:
            update_data["ai_extracted_fields"] = ai_extracted_fields
        if ai_analysis_metadata is not None:
            update_data["ai_analysis_metadata"] = ai_analysis_metadata

        return await self.update(document_id, update_data)

    async def mark_verified(self, document_id: UUID) -> Optional[Document]:
        """Mark document as verified (authentic and valid)."""
        return await self.update(
            document_id,
            {"status": DocumentStatus.VERIFIED},
        )

    async def mark_rejected(
        self, document_id: UUID, reason: Optional[str] = None
    ) -> Optional[Document]:
        """Mark document as rejected (tampered/expired/invalid)."""
        update_data: Dict[str, Any] = {"status": DocumentStatus.REJECTED}
        if reason:
            update_data["ai_verification_notes"] = reason
        return await self.update(document_id, update_data)

    async def mark_error(
        self, document_id: UUID, error_message: str
    ) -> Optional[Document]:
        """Record processing error and increment attempt counter."""
        document = await self.get_by_id(document_id)
        if document is None:
            return None

        return await self.update(
            document_id,
            {
                "status": DocumentStatus.ERROR,
                "processing_error": error_message,
                "processing_attempts": document.processing_attempts + 1,
            },
        )

    async def mark_for_retry(self, document_id: UUID) -> Optional[Document]:
        """Reset document to PENDING for reprocessing."""
        return await self.update(
            document_id,
            {
                "status": DocumentStatus.PENDING,
                "processing_error": None,
            },
        )

    # =========================================================================
    # Query Methods
    # =========================================================================

    async def get_by_submission_id(
        self,
        kyc_submission_id: UUID,
    ) -> List[Document]:
        """
        Get all documents for a KYC submission.

        Args:
            kyc_submission_id: ID of the KYC submission

        Returns:
            List of Document instances ordered by creation time
        """
        stmt = (
            select(Document)
            .where(
                and_(
                    Document.kyc_submission_id == kyc_submission_id,
                    Document.deleted_at.is_(None),
                )
            )
            .order_by(Document.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_submission_and_type(
        self,
        kyc_submission_id: UUID,
        document_type: DocumentType,
    ) -> Optional[Document]:
        """
        Get a specific document type for a KYC submission.

        Args:
            kyc_submission_id: ID of the KYC submission
            document_type: Document type to find

        Returns:
            Most recent document of the specified type, or None
        """
        stmt = (
            select(Document)
            .where(
                and_(
                    Document.kyc_submission_id == kyc_submission_id,
                    Document.document_type == document_type,
                    Document.deleted_at.is_(None),
                )
            )
            .order_by(Document.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_pending_documents(self, limit: int = 50) -> List[Document]:
        """
        Get documents that are pending processing.

        Used by Celery workers to find work to process.

        Args:
            limit: Maximum number of documents to fetch

        Returns:
            List of pending Document instances
        """
        stmt = (
            select(Document)
            .where(
                and_(
                    Document.status.in_([
                        DocumentStatus.PENDING,
                        DocumentStatus.ERROR,  # Include errors for retry
                    ]),
                    Document.processing_attempts < 3,  # Max 3 attempts
                    Document.deleted_at.is_(None),
                )
            )
            .order_by(Document.created_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_file_hash(self, file_hash: str) -> Optional[Document]:
        """
        Look up a document by SHA-256 file hash.

        Used to detect duplicate uploads.

        Args:
            file_hash: SHA-256 hash of the file

        Returns:
            Existing Document if hash found, None otherwise
        """
        return await self.get_by_field("file_hash_sha256", file_hash)

    async def soft_delete_document(self, document_id: UUID) -> Optional[Document]:
        """
        Soft delete a document by setting deleted_at.

        The physical file should be deleted separately.
        """
        return await self.soft_delete(document_id)

    async def count_by_submission(self, kyc_submission_id: UUID) -> int:
        """Count documents for a submission."""
        return await self.count({"kyc_submission_id": kyc_submission_id})

    async def has_required_documents(
        self,
        kyc_submission_id: UUID,
        required_types: List[DocumentType],
    ) -> bool:
        """
        Check if a submission has all required document types.

        Args:
            kyc_submission_id: ID of the submission to check
            required_types: List of required document types

        Returns:
            True if all required types are present with PROCESSED+ status
        """
        for doc_type in required_types:
            doc = await self.get_by_submission_and_type(kyc_submission_id, doc_type)
            if doc is None or doc.status not in (
                DocumentStatus.PROCESSED,
                DocumentStatus.VERIFIED,
            ):
                return False
        return True
