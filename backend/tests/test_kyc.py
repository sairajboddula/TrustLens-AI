"""
Tests for KYC Submission Endpoints

Covers:
  POST /api/v1/kyc/submit
  GET  /api/v1/kyc/submissions
  GET  /api/v1/kyc/submissions/{id}
  GET  /api/v1/kyc/submissions/{id}/status
"""

from __future__ import annotations

import uuid
from typing import Dict, Any
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.kyc import KYCSubmission, KYCStatus, KYCDocumentType


# ---------------------------------------------------------------------------
# Submit KYC
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submit_kyc_success(
    async_client: AsyncClient,
    auth_headers: Dict[str, str],
    sample_kyc_data: Dict[str, Any],
    test_db: AsyncSession,
):
    """An authenticated user can successfully submit a KYC application."""
    # Patch the Celery task so we don't attempt real processing
    with patch("app.services.kyc_service.process_kyc_submission") as mock_task:
        mock_task.delay = MagicMock(return_value=MagicMock(id="fake-task-id"))

        response = await async_client.post(
            "/api/v1/kyc/submit",
            json=sample_kyc_data,
            headers=auth_headers,
        )

    assert response.status_code == 201, response.text
    data = response.json()
    assert "id" in data
    assert "reference_number" in data
    assert data["status"] in ("draft", "submitted", "processing")


@pytest.mark.asyncio
async def test_submit_kyc_requires_authentication(
    async_client: AsyncClient,
    sample_kyc_data: Dict[str, Any],
):
    """Unauthenticated KYC submission is rejected with 401 or 403."""
    response = await async_client.post("/api/v1/kyc/submit", json=sample_kyc_data)
    assert response.status_code in (401, 403), response.text


@pytest.mark.asyncio
async def test_submit_kyc_missing_fields(
    async_client: AsyncClient,
    auth_headers: Dict[str, str],
):
    """Submitting with missing required fields returns 422."""
    incomplete_data = {
        "applicant_first_name": "John",
        # missing last_name, primary_document_type, etc.
    }
    response = await async_client.post(
        "/api/v1/kyc/submit",
        json=incomplete_data,
        headers=auth_headers,
    )
    assert response.status_code == 422, response.text
    error_detail = response.json()
    assert "error" in error_detail or "detail" in error_detail


@pytest.mark.asyncio
async def test_submit_kyc_invalid_document_type(
    async_client: AsyncClient,
    auth_headers: Dict[str, str],
    sample_kyc_data: Dict[str, Any],
):
    """Submitting with an invalid document_type enum returns 422."""
    bad_data = {**sample_kyc_data, "primary_document_type": "floppy_disk"}
    response = await async_client.post(
        "/api/v1/kyc/submit",
        json=bad_data,
        headers=auth_headers,
    )
    assert response.status_code == 422, response.text


# ---------------------------------------------------------------------------
# Get submission status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_submission_status(
    async_client: AsyncClient,
    auth_headers: Dict[str, str],
    test_user: User,
    test_db: AsyncSession,
):
    """A user can retrieve the status of their own submission."""
    # Create a submission directly in DB
    submission = KYCSubmission(
        id=uuid.uuid4(),
        reference_number=f"KYC-TEST-{uuid.uuid4().hex[:8].upper()}",
        user_id=test_user.id,
        applicant_first_name="John",
        applicant_last_name="Doe",
        primary_document_type=KYCDocumentType.PASSPORT,
        status=KYCStatus.PROCESSING,
    )
    test_db.add(submission)
    await test_db.flush()

    response = await async_client.get(
        f"/api/v1/kyc/submissions/{submission.id}/status",
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["submission_id"] == str(submission.id)
    assert "status" in data
    assert data["status"] == "processing"


@pytest.mark.asyncio
async def test_get_submission_not_found(
    async_client: AsyncClient,
    auth_headers: Dict[str, str],
):
    """Requesting a non-existent submission ID returns 404."""
    fake_id = uuid.uuid4()
    response = await async_client.get(
        f"/api/v1/kyc/submissions/{fake_id}/status",
        headers=auth_headers,
    )
    assert response.status_code == 404, response.text


@pytest.mark.asyncio
async def test_get_other_user_submission_forbidden(
    async_client: AsyncClient,
    test_db: AsyncSession,
    test_admin: User,
    auth_headers: Dict[str, str],  # test_user headers
):
    """A user cannot access another user's submission."""
    # Submission owned by admin, accessed by test_user
    submission = KYCSubmission(
        id=uuid.uuid4(),
        reference_number=f"KYC-ADMIN-{uuid.uuid4().hex[:8].upper()}",
        user_id=test_admin.id,
        applicant_first_name="Admin",
        applicant_last_name="User",
        primary_document_type=KYCDocumentType.NATIONAL_ID,
        status=KYCStatus.SUBMITTED,
    )
    test_db.add(submission)
    await test_db.flush()

    response = await async_client.get(
        f"/api/v1/kyc/submissions/{submission.id}",
        headers=auth_headers,
    )
    assert response.status_code in (403, 404), response.text


# ---------------------------------------------------------------------------
# List submissions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_submissions_empty(
    async_client: AsyncClient,
    auth_headers: Dict[str, str],
):
    """List endpoint returns an empty result for a user with no submissions."""
    response = await async_client.get(
        "/api/v1/kyc/submissions",
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert "items" in data
    assert isinstance(data["items"], list)
    assert "total" in data


@pytest.mark.asyncio
async def test_list_submissions_paginated(
    async_client: AsyncClient,
    auth_headers: Dict[str, str],
    test_user: User,
    test_db: AsyncSession,
):
    """List endpoint respects page and size query parameters."""
    # Create 5 submissions
    for i in range(5):
        sub = KYCSubmission(
            id=uuid.uuid4(),
            reference_number=f"KYC-PAGE-{i:04d}",
            user_id=test_user.id,
            applicant_first_name="Test",
            applicant_last_name=f"User{i}",
            primary_document_type=KYCDocumentType.PASSPORT,
            status=KYCStatus.SUBMITTED,
        )
        test_db.add(sub)
    await test_db.flush()

    # Request page 1 with size 2
    response = await async_client.get(
        "/api/v1/kyc/submissions?page=1&size=2",
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data["items"]) <= 2
    assert data["page"] == 1
    assert data["size"] == 2
    assert data["total"] >= 5


@pytest.mark.asyncio
async def test_list_submissions_page_out_of_range(
    async_client: AsyncClient,
    auth_headers: Dict[str, str],
):
    """Requesting page 0 returns 422 validation error."""
    response = await async_client.get(
        "/api/v1/kyc/submissions?page=0",
        headers=auth_headers,
    )
    assert response.status_code == 422, response.text
