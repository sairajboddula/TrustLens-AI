# KYC Platform — API Reference

Base URL: `http://localhost:8000/api/v1`

All endpoints that require authentication expect a Bearer token in the `Authorization` header:

```
Authorization: Bearer <access_token>
```

---

## Table of Contents

1. [Authentication](#1-authentication)
2. [KYC Submissions](#2-kyc-submissions)
3. [Documents](#3-documents)
4. [Admin — Submissions](#4-admin--submissions)
5. [Admin — Workflow](#5-admin--workflow)
6. [System](#6-system)
7. [Error Codes](#7-error-codes)

---

## 1. Authentication

### POST /auth/register

Create a new customer account.

**Request Body**

```json
{
  "email": "john.doe@example.com",
  "username": "johndoe",
  "password": "SecurePass1!",
  "first_name": "John",
  "last_name": "Doe",
  "phone_number": "+15555550100"
}
```

**Password requirements**: ≥8 chars, at least one uppercase, lowercase, digit, and special character.

**Response 201**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "john.doe@example.com",
  "username": "johndoe",
  "first_name": "John",
  "last_name": "Doe",
  "role": "customer",
  "status": "pending_verify",
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Errors**

| Code | Description |
|------|-------------|
| 400 | Email or username already registered |
| 422 | Validation error (weak password, invalid email, etc.) |

---

### POST /auth/login

Authenticate and obtain JWT token pair.

**Request Body**

```json
{
  "username": "john.doe@example.com",
  "password": "SecurePass1!"
}
```

Note: `username` field accepts the user's email address.

**Response 200**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

`expires_in` is in seconds (default: 30 minutes = 1800).

**Errors**

| Code | Description |
|------|-------------|
| 401 | Invalid credentials |
| 403 | Account locked or suspended |
| 422 | Missing or malformed request body |

---

### POST /auth/refresh

Exchange a valid refresh token for a new access token.

**Request Body**

```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response 200**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

**Errors**

| Code | Description |
|------|-------------|
| 401 | Invalid or expired refresh token |

---

### POST /auth/logout

Revoke the current access token.

**Headers**: `Authorization: Bearer <access_token>`

**Response 200**

```json
{ "message": "Successfully logged out." }
```

---

### POST /auth/change-password

Change the authenticated user's password.

**Request Body**

```json
{
  "current_password": "OldPass1!",
  "new_password": "NewPass2@"
}
```

**Response 204** (No Content)

**Errors**

| Code | Description |
|------|-------------|
| 400 | Current password is incorrect |
| 401 | Not authenticated |
| 422 | New password does not meet strength requirements |

---

## 2. KYC Submissions

### POST /kyc/submit

Submit a new KYC application.

**Headers**: `Authorization: Bearer <access_token>`

**Request Body**

```json
{
  "applicant_first_name": "John",
  "applicant_last_name": "Doe",
  "applicant_date_of_birth": "1990-01-15",
  "applicant_nationality": "USA",
  "applicant_address": "123 Main St, Springfield, IL 62701",
  "applicant_phone": "+15555550100",
  "applicant_email": "john.doe@example.com",
  "primary_document_type": "passport",
  "primary_document_number": "AB123456",
  "primary_document_issuing_country": "USA",
  "primary_document_expiry": "2030-01-15"
}
```

**`primary_document_type` values**: `passport`, `national_id`, `drivers_license`, `residence_permit`, `utility_bill`, `bank_statement`, `tax_document`, `selfie`

**Response 201**

```json
{
  "id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
  "reference_number": "KYC-2024-001234",
  "status": "submitted",
  "submitted_at": "2024-01-15T10:35:00Z"
}
```

**Errors**

| Code | Description |
|------|-------------|
| 400 | Max submission attempts exceeded |
| 401 | Not authenticated |
| 403 | Account not active |
| 422 | Validation error (missing fields, invalid enum) |

---

### GET /kyc/submissions

List the authenticated user's KYC submissions (paginated).

**Query Parameters**: `page` (default 1), `size` (default 20, max 100)

**Response 200** — paginated list of submission summaries.

---

### GET /kyc/submissions/{submission_id}

Get full details for a specific submission including documents and AI scores.

**Response 200** — full submission object with `documents[]`, `ai_confidence_score`, `ai_flags`, `risk_level`.

**Errors**

| Code | Description |
|------|-------------|
| 403 | Access denied (not owner, not admin) |
| 404 | Submission not found |

---

### GET /kyc/submissions/{submission_id}/status

Lightweight status polling endpoint.

**Response 200**

```json
{
  "submission_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
  "reference_number": "KYC-2024-001234",
  "status": "processing",
  "ai_confidence_score": null,
  "processing_started_at": "2024-01-15T10:35:05Z",
  "processing_completed_at": null
}
```

---

## 3. Documents

### POST /documents/upload

Upload an identity document file.

**Headers**: `Authorization: Bearer <access_token>`, `Content-Type: multipart/form-data`

**Form Fields**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | File | Yes | Document image or PDF |
| `document_type` | string | Yes | One of the DocumentType enum values |
| `kyc_submission_id` | UUID | No | Associate with an existing submission |

**Accepted MIME types**: `image/jpeg`, `image/png`, `application/pdf`

**Max file size**: 10 MB (configurable via `MAX_FILE_SIZE_MB`)

**Response 201** — document metadata object.

**Errors**

| Code | Description |
|------|-------------|
| 400 | File type not allowed or file too large |
| 401 | Not authenticated |
| 422 | Missing file or invalid document_type |

---

### GET /documents/{document_id}

Get metadata for an uploaded document.

**Response 200** — document metadata including `ocr_confidence` and `ai_authenticity_score` once processed.

---

### DELETE /documents/{document_id}

Soft-delete an uploaded document (owner or admin only).

**Response 204** (No Content)

---

## 4. Admin — Submissions

All admin endpoints require `admin` or `reviewer` role.

### GET /admin/kyc/submissions

List all KYC submissions across all users.

**Query Parameters**

| Name | Type | Description |
|------|------|-------------|
| `page` | integer | Page number |
| `size` | integer | Items per page (max 100) |
| `status` | string | Filter by KYC status |
| `risk_level` | string | Filter by risk level |
| `search` | string | Search by applicant name or reference number |
| `date_from` | string | ISO 8601 date lower bound |
| `date_to` | string | ISO 8601 date upper bound |

**Response 200** — paginated list of `KYCSubmissionSummary` objects.

---

### GET /admin/kyc/submissions/{submission_id}

Full submission details with all AI scores and fraud flags.

**Response 200** — complete submission including `workflow_steps[]`, `final_report`, `admin_decisions[]`, `timeline_events[]`.

---

### POST /admin/kyc/submissions/{submission_id}/override

Manually override the AI decision (approve, reject, or escalate).

**Request Body**

```json
{
  "status": "approved",
  "reason": "All documents verified. Identity confirmed."
}
```

`status` values: `approved`, `rejected`, `under_review`

**Response 200** — updated submission object.

---

### GET /admin/stats

Return dashboard statistics.

**Response 200**

```json
{
  "total_submissions": 1250,
  "by_status": { "approved": 1100, "rejected": 78, "under_review": 15 },
  "by_risk_level": { "low": 900, "medium": 250, "high": 78 },
  "auto_approved": 980,
  "auto_rejected": 60,
  "manual_review": 15,
  "avg_processing_time_seconds": 4.2,
  "approval_rate": 0.934
}
```

---

### GET /admin/stats/submissions-over-time

Daily submission counts for a chart.

**Query Parameters**: `days` (default 30, max 365)

**Response 200** — array of `{ date, total, approved, rejected, pending }` objects.

---

### GET /admin/users

List all registered users (paginated).

**Query Parameters**: `page`, `size`, `role`, `status`, `search`

**Response 200** — paginated list of user objects.

---

## 5. Admin — Workflow

These endpoints power the **Admin Case Detail** page. All require `admin` or `reviewer` role.

### POST /admin/workflow/{submission_id}/start

Trigger the full multi-agent verification pipeline for a KYC case.

Initialises `KYCWorkflowStep` records for all eight pipeline steps then runs the LangGraph graph in a background task. Poll `/status` to track progress.

**Response 202**

```json
{
  "message": "Verification workflow started.",
  "submission_id": "6ba7b810-...",
  "status": "running"
}
```

---

### GET /admin/workflow/{submission_id}/status

Poll current step statuses and overall progress. Call every 2 seconds while `workflow_status === "running"`.

**Response 200**

```json
{
  "submission_id": "6ba7b810-...",
  "workflow_status": "running",
  "progress_pct": 40,
  "steps": [
    {
      "id": "uuid",
      "step_name": "customer_document_analysis",
      "step_order": 2,
      "status": "completed",
      "summary": "Document analysis completed. Type: passport. Quality: 88%. Completeness: 100%.",
      "score": 0.88,
      "started_at": "2024-01-15T10:35:10Z",
      "completed_at": "2024-01-15T10:35:11Z",
      "duration_ms": 840,
      "details": { ... }
    },
    {
      "step_name": "customer_compliance_review",
      "status": "in_progress",
      ...
    },
    {
      "step_name": "government_identity_validation",
      "status": "pending",
      ...
    }
  ],
  "final_recommendation": null,
  "report_available": false
}
```

**`workflow_status` values**: `pending`, `running`, `completed`, `completed_with_errors`

**`step_name` values** (in order): `ingestion`, `document_processing`, `customer_document_analysis`, `customer_compliance_review`, `government_identity_validation`, `identity_verification`, `final_report_generation`, `decision`

**`status` values per step**: `pending`, `in_progress`, `completed`, `failed`, `skipped`

---

### GET /admin/workflow/{submission_id}/report

Retrieve the structured final KYC report generated by the Final Report agent.

**Response 200**

```json
{
  "submission_id": "6ba7b810-...",
  "report": {
    "report_metadata": { "submission_id": "...", "generated_at": "..." },
    "customer_submitted_details": { "first_name": "John", "last_name": "Doe", ... },
    "ocr_extracted_details": { "extracted_name": "John Doe", ... },
    "workflow_results": {
      "document_analysis": { "status": "completed", "quality_score": 0.88, ... },
      "compliance_review": { "status": "passed", "flags": [], ... },
      "government_validation": { "status": "verified", "match_score": 0.94, ... },
      "identity_verification": { "status": "verified", "confidence_score": 0.89, ... }
    },
    "fraud_compliance_flags": { "fraud_flags": [], "compliance_flags": [] },
    "scores_summary": { "final_confidence_score": 0.89, ... },
    "recommended_action": "approve"
  },
  "final_confidence_score": 0.89,
  "recommended_action": "approve",
  "fraud_detected": false,
  "compliance_passed": true,
  "government_validated": true,
  "identity_verified": true,
  "document_quality_score": 0.88,
  "generated_at": "2024-01-15T10:35:20Z"
}
```

**Errors**

| Code | Description |
|------|-------------|
| 404 | Report not yet generated — run the workflow first |

---

### POST /admin/workflow/{submission_id}/approve

Approve the KYC case. Updates `KYCSubmission.status` to `approved`.

**Request Body**

```json
{ "notes": "All checks passed. Identity confirmed." }
```

`notes` is optional.

**Response 200**

```json
{
  "message": "Case approved.",
  "submission_id": "6ba7b810-...",
  "decision": "approved",
  "new_status": "approved"
}
```

---

### POST /admin/workflow/{submission_id}/reject

Reject the KYC case. Updates `KYCSubmission.status` to `rejected`.

**Request Body**

```json
{ "notes": "Document tampering suspected. Sanctions match found." }
```

**Response 200** — same structure as approve.

---

### POST /admin/workflow/{submission_id}/manual-review

Mark the case for manual review. Updates `KYCSubmission.status` to `under_review`.

**Request Body**

```json
{ "notes": "Inconclusive results. Escalating for senior review." }
```

**Response 200** — same structure as approve.

---

### POST /admin/workflow/{submission_id}/notes

Save or update admin notes without changing case status.

**Request Body**

```json
{ "notes": "Verified with branch manager via phone call." }
```

**Response 200**

```json
{ "message": "Notes saved.", "submission_id": "6ba7b810-..." }
```

---

### GET /admin/workflow/{submission_id}/timeline

Return the ordered journey log for a KYC case.

**Response 200**

```json
[
  {
    "id": "uuid",
    "event_type": "WORKFLOW_STARTED",
    "event_title": "Admin Verification Workflow Started",
    "event_detail": "Admin initiated the full ID & verification pipeline.",
    "actor": "admin",
    "occurred_at": "2024-01-15T10:35:00Z"
  },
  {
    "event_type": "STEP_COMPLETED",
    "event_title": "Customer Document Analysis Completed",
    "event_detail": "Document analysis completed. Type: passport. Quality: 88%.",
    "actor": "customer_document_analysis_agent",
    "occurred_at": "2024-01-15T10:35:11Z"
  },
  {
    "event_type": "ADMIN_DECISION",
    "event_title": "Case Approved",
    "event_detail": "All checks passed.",
    "actor": "reviewer@bank.com",
    "occurred_at": "2024-01-15T10:40:00Z"
  }
]
```

**`event_type` values**: `WORKFLOW_STARTED`, `STEP_STARTED`, `STEP_COMPLETED`, `STEP_FAILED`, `ADMIN_DECISION`, `ADMIN_NOTES_SAVED`, `STATUS_CHANGED`, `REPORT_GENERATED`

---

## 6. System

### GET /health

Application health check. No authentication required.

**Response 200**

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "environment": "production",
  "database": "healthy",
  "redis": "healthy"
}
```

`status` can be `healthy` or `degraded` if any dependency is unhealthy.

---

### GET /

API root endpoint.

**Response 200**

```json
{
  "name": "KYC Verification System",
  "version": "1.0.0",
  "docs": "/docs",
  "health": "/health"
}
```

---

## 7. Error Codes

All error responses follow this schema:

```json
{
  "error": {
    "code": 422,
    "message": "Validation error",
    "details": [...],
    "request_id": "3b4a6d2e-9dad-11d1-80b4-00c04fd430c8"
  }
}
```

### HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created |
| 202 | Accepted (background task started) |
| 204 | No Content |
| 400 | Bad Request (business rule violation) |
| 401 | Unauthorized (missing or invalid token) |
| 403 | Forbidden (insufficient permissions) |
| 404 | Not Found |
| 409 | Conflict (duplicate resource) |
| 422 | Unprocessable Entity (validation error) |
| 429 | Too Many Requests (rate limit exceeded) |
| 500 | Internal Server Error |
| 503 | Service Unavailable |

### Common Error Messages

| Message | Cause |
|---------|-------|
| `Token has expired` | JWT access token past its expiry — use refresh token |
| `Token has been revoked` | Token was logged out — obtain a new token pair |
| `Invalid token type` | Refresh token used where access token required |
| `Account is locked` | Too many failed login attempts — contact admin |
| `Email already registered` | POST /auth/register with duplicate email |
| `Submission not found` | Submission ID does not exist or not owned by caller |
| `Max submission attempts exceeded` | User has reached `KYC_MAX_SUBMISSION_ATTEMPTS` limit |
| `Final report not yet generated` | GET /admin/workflow/{id}/report before workflow completes |
