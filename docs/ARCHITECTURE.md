# KYC Platform — Architecture Documentation

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Component Diagram](#2-component-diagram)
3. [LangGraph Agent Flow](#3-langgraph-agent-flow)
4. [Admin Review Workflow](#4-admin-review-workflow)
5. [API Endpoint Reference](#5-api-endpoint-reference)
6. [Database Schema](#6-database-schema)
7. [Security Architecture](#7-security-architecture)
8. [Deployment Guide](#8-deployment-guide)
9. [Performance Considerations](#9-performance-considerations)

---

## 1. System Overview

The KYC (Know Your Customer) Verification Platform is a production-grade identity verification system that automates the KYC compliance process using AI-powered document analysis and a multi-agent LangGraph pipeline.

### Core Capabilities

- **Multi-document support**: Passport, National ID, Driver's License, Residence Permit
- **AI-powered OCR**: EasyOCR extracts text from uploaded identity documents
- **Fuzzy name matching**: RapidFuzz handles OCR imperfections and name ordering variations
- **Extended admin review pipeline**: Five agent-driven stages for thorough case review
- **Compliance screening**: Sanctions, PEP, and high-risk country checks (mock, provider-abstracted)
- **Government identity validation**: Provider-abstracted mock with deterministic outcomes
- **Consolidated identity verification**: Weighted scoring across all pipeline stages
- **Structured final report**: Comprehensive KYC report for admin review with recommended action
- **Fraud detection**: Composite scoring with configurable thresholds
- **Automated decision-making**: APPROVED / REJECTED / MANUAL_REVIEW with full audit trail
- **Role-based access control**: Admin, Reviewer, Customer, Analyst roles
- **Async processing**: Celery + Redis for non-blocking document processing
- **Desktop packaging**: PyInstaller .exe and Electron installer

### Technology Stack

| Layer | Technology |
|-------|------------|
| API | FastAPI 0.110+, Python 3.11+ |
| AI Pipeline | LangGraph, LangChain |
| OCR | EasyOCR |
| Fuzzy Matching | RapidFuzz |
| Compliance / Gov Validation | Mock provider abstraction (swappable) |
| Database | PostgreSQL 15+ (async via asyncpg) |
| Cache/Queue | Redis 7+ |
| Task Queue | Celery 5+ |
| Frontend | React 18+, TypeScript, Vite, Tailwind CSS |
| Containerization | Docker, Docker Compose |
| Desktop | PyInstaller (Python .exe), Electron |

---

## 2. Component Diagram

```
                          ┌───────────────────────────────────────────────────┐
                          │                   KYC Platform                     │
                          │                                                     │
  ┌──────────┐  HTTPS     │  ┌────────────┐    ┌─────────────────────────────┐ │
  │  Browser  │ ────────► │  │   React    │    │      FastAPI Backend          │ │
  │  /Electron│           │  │  Frontend  │◄──►│                             │ │
  └──────────┘            │  │  (Vite)    │    │  ┌───────────────────────┐  │ │
                          │  │            │    │  │    REST API v1         │  │ │
                          │  │  Admin     │    │  │  /auth /kyc /docs     │  │ │
                          │  │  Case      │    │  │  /admin /workflow      │  │ │
                          │  │  Detail    │    │  │  /health               │  │ │
                          │  │  Page      │    │  └──────────┬────────────┘  │ │
                          │  └────────────┘    │             │               │ │
                          │                    │  ┌──────────▼────────────┐  │ │
                          │                    │  │    Service Layer        │  │ │
                          │                    │  │  AuthService           │  │ │
                          │                    │  │  KYCService            │  │ │
                          │                    │  │  DocumentService       │  │ │
                          │                    │  └──────────┬────────────┘  │ │
                          │                    │             │               │ │
                          │                    │  ┌──────────▼────────────┐  │ │
                          │                    │  │  LangGraph Pipeline    │  │ │
                          │                    │  │  (8-node KYC graph)   │  │ │
                          │                    │  │                        │  │ │
                          │                    │  │  Ingestion             │  │ │
                          │                    │  │  DocumentProcessing    │  │ │
                          │                    │  │  DocAnalysis           │  │ │
                          │                    │  │  ComplianceReview      │  │ │
                          │                    │  │  GovValidation         │  │ │
                          │                    │  │  IdentityVerification  │  │ │
                          │                    │  │  FinalReport           │  │ │
                          │                    │  │  Decision              │  │ │
                          │                    │  └──────────┬────────────┘  │ │
                          │                    │             │               │ │
                          │                    │  ┌──────────▼────────────┐  │ │
                          │                    │  │    Celery Workers      │  │ │
                          │                    │  └───────────────────────┘  │ │
                          │                    └─────────────────────────────┘ │
                          │                                  │                  │
                    ┌─────┼────────────┬─────────────────────┼───────────────┐  │
                    │     │            │                      │               │  │
              ┌─────▼───┐ │  ┌─────────▼──────┐  ┌──────────▼─────┐  ┌──────▼─┐
              │PostgreSQL│ │  │    Redis        │  │  File Storage   │  │ Logs   │
              │  (data)  │ │  │(cache + queue)  │  │  (uploads/)     │  │        │
              └──────────┘ │  └────────────────┘  └────────────────┘  └────────┘
                          └───────────────────────────────────────────────────┘
```

---

## 3. LangGraph Agent Flow

The KYC verification pipeline is implemented as a LangGraph `StateGraph`. Each node is a pure function that reads from and writes to the shared `KYCAgentState` TypedDict.

```
START
  │
  ▼
┌─────────────────┐
│ Ingestion Agent │  Validates required fields (first_name, last_name,
└────────┬────────┘  date_of_birth, id_number, id_type, document_ids).
         │           Sanitizes input; validates DOB format and ID-number regex.
         │
         ├─── errors? ──► ┌────────────────┐
         │                │  Error Handler  │ Increments retry_count.
         │                └────────┬────────┘ retry or → decision.
         ▼ success
┌───────────────────────┐
│ Document Processing   │  EasyOCR on uploaded files.
│       Agent           │  Extracts name, DOB, ID number, address.
└──────────┬────────────┘  Persists ocr_results to state.
           ├─── errors? ──► (Error Handler)
           ▼ success
┌───────────────────────────────────┐
│ Customer Document Analysis Agent  │  Assesses document quality (0–1),
└──────────┬────────────────────────┘  completeness (0–1), tamper indicators,
           │                           and detected document type.
           ▼
┌───────────────────────────────────┐
│ Customer Compliance Review Agent  │  Mock sanctions + PEP + high-risk
└──────────┬────────────────────────┘  country + mandatory fields checks.
           │                           Provider: MockComplianceProvider v1.
           ▼
┌────────────────────────────────────────┐
│ Government Identity Validation Agent   │  Provider-abstracted validation.
└──────────┬─────────────────────────────┘  MockGovernmentValidationProvider
           │                                (80% pass, deterministic via SHA-256).
           ▼
┌───────────────────────────────────┐
│   Identity Verification Agent     │  Consolidates OCR match scores,
└──────────┬────────────────────────┘  compliance status, gov validation,
           │                           doc quality into a single confidence score.
           ▼
┌───────────────────────────────────┐
│  Final Report Generation Agent    │  Builds structured KYC report.
└──────────┬────────────────────────┘  Persists to kyc_final_reports table.
           │                           Determines recommended action.
           ▼
┌───────────────────────┐
│   Decision Agent      │  confidence ≥ 0.78 AND compliance passed → APPROVED
└──────────┬────────────┘  confidence < 0.45 OR fraud flag → REJECTED
           │               otherwise → MANUAL_REVIEW
           │               Risk: ≥0.80→LOW, ≥0.60→MEDIUM, ≥0.40→HIGH, else CRITICAL
           ▼
          END
```

### State Object (`KYCAgentState`)

#### Core Fields

| Field | Type | Description |
|-------|------|-------------|
| `kyc_submission_id` | str | UUID of the KYCSubmission record |
| `user_id` | str | UUID of the submitting user |
| `form_data` | dict | Sanitized applicant form fields |
| `document_ids` | list[str] | UUIDs of uploaded documents |
| `current_agent` | str | Name of the last agent that ran |
| `retry_count` | int | Error handler retry counter |
| `errors` | list[str] | Accumulated errors |
| `ocr_results` | list[dict] | Per-document OCR output |
| `extracted_name` | str? | Name extracted from primary document |
| `extracted_dob` | str? | DOB extracted (YYYY-MM-DD) |
| `extracted_id_number` | str? | ID number extracted from document |
| `name_match_score` | float? | Fuzzy name similarity (0–1) |
| `dob_match` | bool? | Whether DOB matched |
| `id_match` | bool? | Whether ID number matched |
| `fraud_flags` | list[str] | Fraud indicator strings |
| `duplicate_detected` | bool? | Whether duplicate submission found |
| `confidence_score` | float? | Overall weighted confidence (0–1) |
| `risk_level` | str? | LOW / MEDIUM / HIGH / CRITICAL |
| `decision` | str? | APPROVED / REJECTED / MANUAL_REVIEW |
| `decision_reason` | str? | Human-readable explanation |
| `started_at` | str | ISO 8601 pipeline start timestamp |
| `completed_at` | str? | ISO 8601 pipeline end timestamp |
| `processing_time_ms` | int? | Total processing time |

#### Customer Document Analysis Fields

| Field | Type | Description |
|-------|------|-------------|
| `document_analysis_status` | str? | completed / failed / skipped |
| `document_quality_score` | float? | Image quality score (0–1) |
| `document_tampering_flag` | bool? | Tampering indicators found |
| `document_type_detected` | str? | Detected document type |
| `document_completeness_score` | float? | Mandatory field completeness (0–1) |
| `document_analysis_summary` | str? | Human-readable summary |
| `document_analysis_details` | dict? | Per-check structured output |

#### Customer Compliance Review Fields

| Field | Type | Description |
|-------|------|-------------|
| `compliance_status` | str? | passed / flagged / failed |
| `compliance_flags` | list[str]? | Raised compliance flags |
| `compliance_summary` | str? | Summary text |
| `compliance_details` | dict? | Per-rule check results |
| `pep_result` | bool? | PEP check hit |
| `sanctions_result` | bool? | Sanctions check hit |

#### Government Identity Validation Fields

| Field | Type | Description |
|-------|------|-------------|
| `government_validation_status` | str? | verified / not_verified / error |
| `government_match_score` | float? | Match confidence (0–1) |
| `government_reference_id` | str? | Gov reference (e.g. GOV-REF-XXXXXXXX) |
| `government_validation_summary` | str? | Human-readable summary |
| `government_validation_details` | dict? | Per-field match details |

#### Identity Verification Fields

| Field | Type | Description |
|-------|------|-------------|
| `identity_verification_status` | str? | verified / unverified / inconclusive |
| `identity_confidence_score` | float? | Consolidated confidence (0–1) |
| `fraud_flag` | bool? | Overall fraud determination |
| `identity_verification_summary` | str? | Summary |
| `identity_verification_details` | dict? | Component scores used |

#### Final Report Fields

| Field | Type | Description |
|-------|------|-------------|
| `final_report` | dict? | Full structured KYC report |
| `final_recommendation` | str? | approve / reject / manual_review |
| `report_generated_at` | str? | ISO 8601 timestamp |

---

## 4. Admin Review Workflow

### Overview

The admin review workflow is a five-stage pipeline that runs after initial document OCR processing. It is triggered by clicking **Run ID & Verification** on the Case Detail page.

```
┌──────────────────────────────────────────────────────────────┐
│                    Admin Case Detail Page                      │
│                                                                │
│  ┌─────────────────┐  ┌──────────────────┐  ┌─────────────┐  │
│  │  Journey Log     │  │ Workflow Panel   │  │ Final Report│  │
│  │  (Timeline)      │  │ (5-step stepper) │  │ Viewer      │  │
│  │                  │  │                  │  │             │  │
│  │  • Workflow      │  │  ① Doc Analysis  │  │  Scores     │  │
│  │    Started       │  │  ② Compliance    │  │  Flags      │  │
│  │  • Step events   │  │  ③ Gov Valid     │  │  Sections   │  │
│  │  • Admin actions │  │  ④ Identity Ver  │  │  Raw JSON   │  │
│  │                  │  │  ⑤ Final Report  │  │             │  │
│  └─────────────────┘  └──────────────────┘  └─────────────┘  │
│                                                                │
│  Admin Notes field                                             │
│  [ Approve ] [ Reject ] [ Manual Review ]                     │
└──────────────────────────────────────────────────────────────┘
```

### Stage Details

| Stage | Agent | Key Outputs |
|-------|-------|-------------|
| Customer Document Analysis | `customer_document_analysis_agent` | quality_score, completeness_score, tampering_flag |
| Customer Compliance Review | `customer_compliance_review_agent` | compliance_status, flags (sanctions/PEP/high-risk) |
| Government Identity Validation | `government_identity_validation_agent` | validation_status, match_score, reference_id |
| Identity Verification | `identity_verification_agent` (+ `verification_agent`) | identity_confidence_score, fraud_flag |
| Final Report Generation | `final_report_agent` | final_report dict, recommended_action |

### Provider Abstraction

Both the Compliance Review and Government Validation agents use a provider interface:

```
GovernmentValidationProvider (interface)
  └── MockGovernmentValidationProvider   ← current (demo, deterministic)
  └── RealGovernmentAPIProvider          ← future real integration

MockComplianceProvider (interface)
  └── (swap to real sanctions/PEP API by replacing _PROVIDER at module level)
```

### Workflow Step Tracking

Every agent execution writes a `KYCWorkflowStep` record and a `KYCTimeline` event to the database. The frontend polls `/admin/workflow/{id}/status` every 2 seconds and re-renders the stepper live.

### Decision Flow

```
Admin clicks "Run ID & Verification"
  → POST /admin/workflow/{id}/start
  → Background task: graph.invoke(initial_state)
  → Each agent writes step records to DB
  → Frontend polls /status every 2 s
  → Report available → admin reviews
  → Admin clicks Approve / Reject / Manual Review
  → POST /admin/workflow/{id}/approve (or /reject / /manual-review)
  → KYCSubmission.status updated
  → KYCAdminDecision + KYCTimeline records created
```

---

## 5. API Endpoint Reference

All endpoints are prefixed with `/api/v1`.

### Authentication

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/register` | None | Register new user account |
| POST | `/auth/login` | None | Authenticate; returns JWT pair |
| POST | `/auth/refresh` | None | Exchange refresh token for new access token |
| POST | `/auth/logout` | Bearer | Revoke current access token |
| POST | `/auth/change-password` | Bearer | Change authenticated user's password |

### KYC

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/kyc/submit` | Bearer | Submit new KYC application |
| GET | `/kyc/submissions` | Bearer | List caller's submissions (paginated) |
| GET | `/kyc/submissions/{id}` | Bearer | Full submission details |
| GET | `/kyc/submissions/{id}/status` | Bearer | Lightweight status polling |

### Documents

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/documents/upload` | Bearer | Upload identity document file |
| GET | `/documents/{id}` | Bearer | Get document metadata |
| DELETE | `/documents/{id}` | Bearer | Delete uploaded document |

### Admin — Submissions

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/admin/kyc/submissions` | Admin/Reviewer | List all submissions (paginated, filterable) |
| GET | `/admin/kyc/submissions/{id}` | Admin/Reviewer | Full submission details with AI scores |
| POST | `/admin/kyc/submissions/{id}/override` | Admin/Reviewer | Manual approve/reject/escalate |
| GET | `/admin/stats` | Admin/Reviewer | Dashboard statistics |
| GET | `/admin/stats/submissions-over-time` | Admin/Reviewer | Daily submission chart data |
| GET | `/admin/users` | Admin | List all users |

### Admin — Workflow (new)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/admin/workflow/{id}/start` | Admin/Reviewer | Start the full verification pipeline |
| GET | `/admin/workflow/{id}/status` | Admin/Reviewer | Poll workflow step statuses and progress |
| GET | `/admin/workflow/{id}/report` | Admin/Reviewer | Get the generated final KYC report |
| POST | `/admin/workflow/{id}/approve` | Admin/Reviewer | Approve the KYC case |
| POST | `/admin/workflow/{id}/reject` | Admin/Reviewer | Reject the KYC case |
| POST | `/admin/workflow/{id}/manual-review` | Admin/Reviewer | Mark for manual review |
| POST | `/admin/workflow/{id}/notes` | Admin/Reviewer | Save admin notes |
| GET | `/admin/workflow/{id}/timeline` | Admin/Reviewer | Get ordered timeline events |

### System

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | None | Application health check |
| GET | `/` | None | API root (name, version, docs link) |

---

## 6. Database Schema

### Core Tables (existing)

```
users ──1:N──► kyc_submissions ──1:N──► documents
                                └──1:N──► audit_logs
```

### Workflow Tables (new — migration 004)

```
kyc_submissions ──1:N──► kyc_workflow_steps
                └──1:1──► kyc_final_reports
                └──1:N──► kyc_admin_decisions
                └──1:N──► kyc_timeline
```

#### `kyc_workflow_steps`

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID PK | |
| `submission_id` | UUID FK | Parent submission |
| `step_name` | ENUM | One of 8 pipeline step names |
| `step_order` | INTEGER | 0-based display order |
| `status` | ENUM | pending / in_progress / completed / failed / skipped |
| `summary` | TEXT | Human-readable outcome |
| `details` | JSON | Structured agent output |
| `score` | FLOAT | Primary score (0–1) from this step |
| `started_at` | TIMESTAMPTZ | Step execution start |
| `completed_at` | TIMESTAMPTZ | Step execution end |
| `duration_ms` | INTEGER | Execution duration |

**Enum `workflow_step_name_enum`**: `ingestion`, `document_processing`, `customer_document_analysis`, `customer_compliance_review`, `government_identity_validation`, `identity_verification`, `final_report_generation`, `decision`

**Enum `workflow_step_status_enum`**: `pending`, `in_progress`, `completed`, `failed`, `skipped`

#### `kyc_final_reports`

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID PK | |
| `submission_id` | UUID FK UNIQUE | One report per submission |
| `report_data` | JSON | Full structured report |
| `final_confidence_score` | FLOAT | Consolidated score |
| `recommended_action` | VARCHAR(50) | approve / reject / manual_review |
| `fraud_detected` | BOOLEAN | |
| `compliance_passed` | BOOLEAN | |
| `government_validated` | BOOLEAN | |
| `identity_verified` | BOOLEAN | |
| `document_quality_score` | FLOAT | |
| `document_tampered` | BOOLEAN | |
| `generated_at` | TIMESTAMPTZ | |

#### `kyc_admin_decisions`

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID PK | |
| `submission_id` | UUID FK | |
| `admin_id` | UUID FK (users) | Decision author |
| `decision_type` | ENUM | approved / rejected / manual_review |
| `notes` | TEXT | Admin's reasoning |
| `decided_at` | TIMESTAMPTZ | |

**Enum `admin_decision_type_enum`**: `approved`, `rejected`, `manual_review`

#### `kyc_timeline`

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID PK | |
| `submission_id` | UUID FK | |
| `event_type` | VARCHAR(100) | WORKFLOW_STARTED, STEP_STARTED, STEP_COMPLETED, STEP_FAILED, ADMIN_DECISION, … |
| `event_title` | VARCHAR(255) | Short display title |
| `event_detail` | TEXT | Longer description |
| `actor` | VARCHAR(100) | Agent name or admin username |
| `metadata` | JSON | Additional structured data |
| `occurred_at` | TIMESTAMPTZ | |

### KYC Submission Status Flow

```
DRAFT → SUBMITTED → PROCESSING → APPROVED
                              → REJECTED
                              → UNDER_REVIEW → APPROVED
                                             → REJECTED
                  → EXPIRED
                  → CANCELLED (user action)
```

### Migration History

| Revision | Description |
|----------|-------------|
| `001_initial_schema` | users, kyc_submissions, documents, audit_logs |
| `002_fix_audit_logs` | Audit log schema fix |
| `003_extend_nationality_column` | Extended nationality field |
| `004_admin_workflow` | kyc_workflow_steps, kyc_final_reports, kyc_admin_decisions, kyc_timeline |

---

## 7. Security Architecture

### Authentication

- **JWT (HS256)**: Access tokens (30 min expiry) + Refresh tokens (7 days).
- **Token revocation**: JTI (JWT ID) blocklist stored in Redis with TTL matching token expiry.
- **Password hashing**: bcrypt with cost factor 12.
- **Account lockout**: After 5 consecutive failed login attempts.

### Authorization

Role-based access control with four roles:

| Role | Permissions |
|------|------------|
| `admin` | Full access: users, all submissions, system config, workflow decisions |
| `reviewer` | Read all submissions; run workflow; approve/reject/manual-review |
| `customer` | Create and read own submissions only |
| `analyst` | Read-only access to anonymized reporting data |

### API Security

- **CORS**: Configurable allowed origins (restrictive by default).
- **Rate limiting**: Per-IP request throttling via Redis counters.
- **Trusted hosts**: Host header validation in production.
- **Security headers**: CSP, X-Frame-Options, HSTS, X-Content-Type-Options.
- **Request IDs**: Every request gets a UUID for tracing.

### Data Security

- **File integrity**: SHA-256 hash stored for every uploaded document.
- **File type validation**: MIME type whitelist (JPEG, PNG, PDF).
- **File size limit**: Configurable (default 10 MB).
- **Soft deletes**: Users and documents are never hard-deleted.
- **Audit trail**: Every state-changing operation is logged to `audit_logs` and `kyc_timeline`.

### Secrets Management

All secrets are loaded from environment variables (never hardcoded):

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | Application secret (≥32 chars) |
| `JWT_SECRET_KEY` | JWT signing key (≥32 chars) |
| `POSTGRES_PASSWORD` | Database password |
| `REDIS_PASSWORD` | Redis auth password |
| `OPENAI_API_KEY` | LLM provider API key |

---

## 8. Deployment Guide

### Docker Compose (Recommended)

```bash
# 1. Copy and configure environment
cp backend/.env.example backend/.env
# Edit backend/.env with production values

# 2. Start all services
docker-compose up -d

# 3. Run all database migrations (including admin workflow tables)
docker-compose exec backend alembic upgrade head

# 4. Create admin user (optional CLI)
docker-compose exec backend python -m app.scripts.create_admin
```

Services started:
- `backend`  — FastAPI on port 8000
- `frontend` — React dev server on port 3000
- `postgres`  — PostgreSQL 15 on port 5432
- `redis`     — Redis 7 on port 6379
- `celery`    — Celery worker

### Production Checklist

- [ ] Set `ENVIRONMENT=production` and `DEBUG=false`
- [ ] Generate strong random `SECRET_KEY` and `JWT_SECRET_KEY` (≥32 chars)
- [ ] Set `ALLOWED_HOSTS` to your domain(s)
- [ ] Set `CORS_ORIGINS` to your frontend origin only
- [ ] Configure HTTPS/TLS (Nginx or AWS ALB)
- [ ] Run `alembic upgrade head` before first start
- [ ] Configure Redis password (`REDIS_PASSWORD`)
- [ ] Set up database backups
- [ ] Configure log aggregation (`LOG_FORMAT=json` for structured logging)

### Database Migrations

```bash
# Apply all pending migrations
alembic upgrade head

# Create a new migration
alembic revision --autogenerate -m "description"

# Downgrade one revision
alembic downgrade -1
```

---

## 9. Performance Considerations

### Async I/O

The entire backend is async-first:
- **asyncpg** for non-blocking PostgreSQL access
- **redis.asyncio** for non-blocking Redis operations
- **httpx** for any outbound HTTP calls
- FastAPI's async request handlers throughout

Admin workflow pipeline agents are synchronous internally but run in a `ThreadPoolExecutor` via `BackgroundTasks` so they do not block the API event loop.

### Database Optimization

- Connection pool: `pool_size=10`, `max_overflow=20`
- All high-cardinality columns are indexed (`email`, `status`, `user_id`, `created_at`, `submission_id`)
- New workflow tables indexed on `submission_id`, `step_name`, `status`, `occurred_at`
- `expire_on_commit=False` prevents lazy-load issues in async sessions
- `pool_pre_ping=True` validates connections before use

### Caching Strategy

- User authentication payloads: cached via JWT (no DB lookup on every request)
- Token revocation: O(1) Redis lookup by JTI
- Submission status: cache-friendly (status rarely changes once terminal)
- Rate limiting: sliding window counters in Redis

### Document Processing

- OCR is CPU/GPU-intensive; offloaded to Celery workers
- Workers can scale horizontally (multiple Celery worker processes)
- `OCR_GPU=true` enables GPU acceleration if CUDA is available
- Large images are preprocessed (resize, greyscale) before OCR

### Admin Workflow Polling

- Frontend polls `/admin/workflow/{id}/status` every 2 seconds while `workflow_status === 'running'`
- Polling stops automatically when status transitions to `completed` or `completed_with_errors`
- No websocket dependency — works through firewalls and in desktop mode

### Scaling

| Bottleneck | Solution |
|------------|----------|
| API throughput | Horizontal FastAPI replicas behind load balancer |
| OCR processing | More Celery workers, GPU instances |
| Admin pipeline | Pipeline runs as background task; multiple requests execute concurrently |
| Database | Read replicas for reporting queries, connection pooling |
| File storage | Move from local filesystem to S3-compatible object storage |
