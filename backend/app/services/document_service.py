"""
Document Service

Handles the full document lifecycle within a KYC submission:
  - Uploading and persisting document files
  - Retrieving document metadata
  - Fetching OCR results
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging_config import get_logger
from app.models.document import Document, DocumentStatus, DocumentType
from app.utils.file_utils import (
    get_file_hash,
    save_uploaded_file,
    validate_file_size,
    validate_file_type,
)

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Upload document
# ---------------------------------------------------------------------------


async def upload_document(
    db: AsyncSession,
    user_id: str | UUID,
    submission_id: str | UUID,
    file: UploadFile,
    doc_type: str,
) -> Document:
    """
    Validate, persist, and register an uploaded identity document.

    Validation:
      - File type (MIME + extension whitelist)
      - File size (max from settings)

    Args:
        db:            Async DB session.
        user_id:       ID of the uploading user (used for audit).
        submission_id: Associated KYC submission ID.
        file:          FastAPI UploadFile instance.
        doc_type:      DocumentType string (e.g. "passport").

    Returns:
        Created Document ORM instance.

    Raises:
        HTTPException 400: If file validation fails.
        HTTPException 422: If doc_type is invalid.
    """
    # Validate document type
    try:
        doc_type_enum = DocumentType(doc_type.lower())
    except ValueError:
        valid_types = [t.value for t in DocumentType]
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid document type '{doc_type}'. Valid types: {valid_types}",
        )

    # Validate MIME type and extension
    filename = file.filename or "upload"
    content_type = file.content_type or ""
    is_valid_type, type_error = validate_file_type(filename, content_type)
    if not is_valid_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=type_error,
        )

    # Read content for hashing + size validation
    content = await file.read()
    await file.seek(0)

    max_size_mb = settings.MAX_FILE_SIZE_MB
    if len(content) > max_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"File size {len(content) / (1024*1024):.2f} MB exceeds "
                f"the maximum allowed size of {max_size_mb} MB."
            ),
        )

    # Save to disk
    stored_filename, storage_path = await save_uploaded_file(file, settings.UPLOAD_DIR)

    # Validate size of saved file
    is_valid_size, size_error = validate_file_size(storage_path, max_size_mb)
    if not is_valid_size:
        import os  # noqa: PLC0415
        os.unlink(storage_path)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=size_error)

    # Compute hash
    file_hash = get_file_hash(storage_path)

    # Detect image dimensions (optional, for image files)
    image_width: Optional[int] = None
    image_height: Optional[int] = None
    image_dpi: Optional[int] = None

    if content_type.startswith("image/"):
        try:
            from PIL import Image  # noqa: PLC0415
            import io  # noqa: PLC0415

            img = Image.open(io.BytesIO(content))
            image_width, image_height = img.size
            dpi_info = img.info.get("dpi")
            if dpi_info:
                image_dpi = int(dpi_info[0])
        except Exception:
            pass  # Non-critical – proceed without dimensions

    import os  # noqa: PLC0415
    file_size = os.path.getsize(storage_path)

    document = Document(
        kyc_submission_id=submission_id,
        document_type=doc_type_enum,
        status=DocumentStatus.PENDING,
        original_filename=filename,
        stored_filename=stored_filename,
        storage_path=storage_path,
        file_size_bytes=file_size,
        mime_type=content_type or "application/octet-stream",
        file_hash_sha256=file_hash,
        image_width=image_width,
        image_height=image_height,
        image_dpi=image_dpi,
    )

    db.add(document)
    await db.flush()

    logger.info(
        "Document uploaded",
        document_id=str(document.id),
        submission_id=str(submission_id),
        doc_type=doc_type,
        file_size_bytes=file_size,
    )
    return document


# ---------------------------------------------------------------------------
# Retrieve document metadata
# ---------------------------------------------------------------------------


async def get_document(
    db: AsyncSession,
    document_id: str | UUID,
    user_id: str | UUID,
) -> Document:
    """
    Retrieve document metadata, enforcing ownership via the KYC submission.

    Raises:
        HTTPException 404: If not found or user does not own the submission.
    """
    from app.models.kyc import KYCSubmission  # noqa: PLC0415

    result = await db.execute(
        select(Document)
        .join(KYCSubmission, Document.kyc_submission_id == KYCSubmission.id)
        .where(
            Document.id == document_id,
            KYCSubmission.user_id == user_id,
        )
    )
    document: Optional[Document] = result.scalar_one_or_none()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )
    return document


# ---------------------------------------------------------------------------
# Get OCR results
# ---------------------------------------------------------------------------


async def get_ocr_results(
    db: AsyncSession,
    document_id: str | UUID,
) -> Dict[str, Any]:
    """
    Return the OCR data associated with a document.

    Args:
        db:          Async DB session.
        document_id: UUID of the Document record.

    Returns:
        Dict with OCR fields.

    Raises:
        HTTPException 404: If document not found.
        HTTPException 425: If OCR has not yet been completed.
    """
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    document: Optional[Document] = result.scalar_one_or_none()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    if document.status == DocumentStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_425_TOO_EARLY,
            detail="OCR processing has not yet completed for this document.",
        )

    return {
        "document_id": str(document.id),
        "status": document.status.value,
        "ocr_raw_text": document.ocr_raw_text,
        "ocr_structured_data": document.ocr_structured_data,
        "ocr_confidence": document.ocr_confidence,
        "ocr_language_detected": document.ocr_language_detected,
        "ocr_processing_time_ms": document.ocr_processing_time_ms,
        "ai_extracted_fields": document.ai_extracted_fields,
        "ai_authenticity_score": document.ai_authenticity_score,
        "ai_tamper_detected": document.ai_tamper_detected,
        "processed_at": document.processed_at.isoformat() if document.processed_at else None,
    }
