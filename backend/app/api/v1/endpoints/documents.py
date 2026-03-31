"""
Document Endpoints

POST /documents/upload        – Upload a KYC identity document
GET  /documents/{id}          – Get document metadata
GET  /documents/{id}/ocr      – Get OCR extraction results
"""

from __future__ import annotations

from typing import Any, Dict
from uuid import UUID

from fastapi import APIRouter, Depends, Form, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.core.logging_config import get_logger
from app.models.user import User
from app.schemas.document import DocumentResponse, DocumentUploadResponse
from app.services.document_service import get_document, get_ocr_results, upload_document

router = APIRouter(prefix="/documents", tags=["Documents"])
logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Upload document
# ---------------------------------------------------------------------------


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a KYC identity document",
    description=(
        "Upload an identity document (JPEG, PNG, or PDF) as part of a KYC submission. "
        "The returned document_id should be passed to POST /kyc/submit. "
        "Accepted file types: image/jpeg, image/png, application/pdf (max 10 MB)."
    ),
)
async def upload_kyc_document(
    file: UploadFile,
    submission_id: UUID = Form(
        ...,
        description="UUID of the KYC submission this document belongs to",
    ),
    doc_type: str = Form(
        ...,
        description="Document type: passport | national_id_front | national_id_back | "
                    "drivers_license_front | drivers_license_back | selfie_photo | other",
    ),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentUploadResponse:
    """Upload an identity document and associate it with a KYC submission."""
    document = await upload_document(
        db=db,
        user_id=current_user.id,
        submission_id=submission_id,
        file=file,
        doc_type=doc_type,
    )
    await db.commit()
    await db.refresh(document)

    logger.info(
        "Document uploaded via API",
        document_id=str(document.id),
        submission_id=str(submission_id),
        user_id=str(current_user.id),
        doc_type=doc_type,
    )

    return DocumentUploadResponse(
        document_id=document.id,
        kyc_submission_id=document.kyc_submission_id,
        document_type=document.document_type,
        original_filename=document.original_filename,
        file_size_mb=document.file_size_mb,
        status=document.status,
        message="Document uploaded successfully. Processing will begin shortly.",
        created_at=document.created_at,
    )


# ---------------------------------------------------------------------------
# Get document metadata
# ---------------------------------------------------------------------------


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get document metadata",
    description=(
        "Retrieve full document metadata for a specific document. "
        "Users can only access documents belonging to their own KYC submissions."
    ),
)
async def get_document_info(
    document_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """Retrieve document information by ID."""
    document = await get_document(
        db=db,
        document_id=document_id,
        user_id=current_user.id,
    )
    return DocumentResponse.from_model(document)


# ---------------------------------------------------------------------------
# Get OCR results
# ---------------------------------------------------------------------------


@router.get(
    "/{document_id}/ocr",
    response_model=Dict[str, Any],
    summary="Get OCR extraction results",
    description=(
        "Return the OCR text extraction results for a processed document. "
        "Returns HTTP 425 if processing has not yet completed."
    ),
)
async def get_document_ocr(
    document_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve OCR results for a document."""
    # Verify document ownership before returning OCR data
    await get_document(db=db, document_id=document_id, user_id=current_user.id)

    ocr_data = await get_ocr_results(db=db, document_id=document_id)
    return ocr_data
