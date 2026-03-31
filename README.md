# KYC Verification Platform

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green?logo=fastapi)
![React](https://img.shields.io/badge/React-18+-61DAFB?logo=react)
![LangGraph](https://img.shields.io/badge/LangGraph-AI%20Pipeline-orange)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-336791?logo=postgresql)
![Redis](https://img.shields.io/badge/Redis-7+-DC382D?logo=redis)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker)
![License](https://img.shields.io/badge/License-MIT-yellow)

A production-grade Know Your Customer (KYC) verification platform with an AI-powered multi-agent pipeline for automated identity document verification and a full admin review workflow.

---

## Features

- **AI-Powered Document Verification**: Extended 8-node LangGraph pipeline with EasyOCR, fuzzy name matching (RapidFuzz), fraud detection, and confidence scoring.
- **Admin Review Workflow**: Five-stage agent-driven review — Document Analysis → Compliance Review → Government Identity Validation → Identity Verification → Final Report Generation.
- **One-Click Verification**: "Run ID & Verification" button triggers all five stages sequentially; UI updates live via polling.
- **Multi-Document Support**: Passport, National ID, Driver's License, Residence Permit, Utility Bill, Bank Statement.
- **Automated Decision Engine**: APPROVED / REJECTED / MANUAL_REVIEW with configurable thresholds and final report.
- **Role-Based Access Control**: Admin, Reviewer, Customer, and Analyst roles with JWT authentication.
- **Async Processing**: Celery + Redis for non-blocking document processing.
- **Complete Audit Trail**: Timeline events and audit logs for every state-changing operation.
- **Desktop Application**: Distributable `.exe` (PyInstaller) and installer (Electron).
- **Docker-Ready**: Full docker-compose stack for one-command deployment.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI 0.110+, Python 3.11+, uvicorn |
| AI Pipeline | LangGraph, LangChain |
| OCR | EasyOCR |
| Fuzzy Matching | RapidFuzz |
| Compliance / Gov Validation | Mock provider abstraction (swappable) |
| Database | PostgreSQL 15+ via asyncpg |
| Cache / Queue | Redis 7+ |
| Task Queue | Celery 5+ |
| Authentication | JWT (python-jose) + bcrypt (passlib) |
| ORM | SQLAlchemy 2.0 (async) |
| Migrations | Alembic |
| Frontend | React 18+, TypeScript, Vite |
| Containerization | Docker, Docker Compose |
| Desktop (Python) | PyInstaller |
| Desktop (Electron) | Electron 28+, electron-builder |
| Testing | pytest, pytest-asyncio, httpx |

---

## Architecture Diagram

```
  ┌────────────┐   HTTP    ┌──────────────────────────────────────────────┐
  │  Browser /  │ ────────► │              FastAPI Backend                  │
  │  Electron   │           │                                               │
  └────────────┘           │  REST API  ►  Service Layer                   │
                           │              ►  LangGraph Pipeline (8 nodes)  │
                           │                 IngestionAgent                 │
                           │                 DocumentProcessingAgent        │
                           │                 CustomerDocumentAnalysisAgent  │
                           │                 CustomerComplianceReviewAgent  │
                           │                 GovernmentIdentityValidAgent   │
                           │                 IdentityVerificationAgent      │
                           │                 FinalReportAgent               │
                           │                 DecisionAgent                  │
                           │              ►  Celery Workers                 │
                           └────────────┬─────────────────────────────────┘
                                        │
                     ┌──────────────────┼───────────────────┐
                     │                  │                   │
               ┌─────▼───┐    ┌────────▼──────┐  ┌────────▼──────┐
               │PostgreSQL│    │     Redis      │  │ File Storage  │
               └──────────┘    └───────────────┘  └───────────────┘
```

---

## Quick Start

### Option A: Docker Compose (Recommended)

**Prerequisites**: Docker Desktop with Compose v2+

```bash
# 1. Clone the repository
git clone <repository-url>
cd KYC

# 2. Configure environment
cp backend/.env.example backend/.env
# Edit backend/.env — at minimum set SECRET_KEY, JWT_SECRET_KEY

# 3. Start all services
docker-compose up -d

# 4. Run database migrations
docker-compose exec backend alembic upgrade head

# 5. Access the application
#    Frontend:      http://localhost:3000
#    API:           http://localhost:8000
#    Swagger Docs:  http://localhost:8000/docs
```

### Option B: Local Development

**Prerequisites**: Python 3.11+, Node.js 18+, PostgreSQL 15+, Redis 7+

```bash
# --- Backend ---
cd backend
python -m venv venv
source venv/bin/activate        # Linux/macOS
# venv\Scripts\activate         # Windows

pip install -r requirements.txt
cp .env.example .env            # edit with your DB/Redis URLs
alembic upgrade head
uvicorn main:app --reload --port 8000

# --- Frontend (separate terminal) ---
cd frontend
npm install
npm run dev                     # starts on http://localhost:3000
```

---

## Environment Variables Reference

All variables are loaded from `backend/.env`. Copy `backend/.env.example` as a starting point.

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | Application secret (≥32 chars) | `$(openssl rand -hex 32)` |
| `JWT_SECRET_KEY` | JWT signing key (≥32 chars) | `$(openssl rand -hex 32)` |
| `DATABASE_URL` | Async PostgreSQL URL | `postgresql+asyncpg://user:pass@localhost/kyc_db` |
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` |

### LLM Provider (at least one required)

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key |
| `GOOGLE_API_KEY` | Google (Gemini) API key |
| `LLM_PROVIDER` | `openai` or `google` (default: `openai`) |

### KYC Business Rules

| Variable | Default | Description |
|----------|---------|-------------|
| `KYC_AUTO_APPROVE_THRESHOLD` | `0.95` | Min confidence for auto-approval |
| `KYC_AUTO_REJECT_THRESHOLD` | `0.30` | Max confidence before auto-rejection |
| `KYC_REVIEW_REQUIRED_THRESHOLD` | `0.70` | Below this → manual review |
| `KYC_MAX_SUBMISSION_ATTEMPTS` | `3` | Max KYC submissions per user |

### Full reference

See `backend/app/core/config.py` for the complete annotated settings class.

---

## LangGraph Agent Flow

```
START
  │
  ├─► Ingestion Agent
  ├─► Document Processing Agent
  ├─► Customer Document Analysis Agent   ─┐
  ├─► Customer Compliance Review Agent    │  Admin Review
  ├─► Government Identity Validation Agent│  Pipeline
  ├─► Identity Verification Agent         │  (5 stages)
  ├─► Final Report Generation Agent      ─┘
  ├─► Decision Agent
  └─► END

Error Handler (retries for Ingestion + Document Processing)
```

| Agent | Responsibility |
|-------|---------------|
| **Ingestion** | Validates and sanitises form data; checks ID format and DOB. |
| **Document Processing** | Runs EasyOCR on uploaded files; extracts name, DOB, ID number. |
| **Customer Document Analysis** | Scores document quality, completeness, and tampering indicators. |
| **Customer Compliance Review** | Mock sanctions, PEP, high-risk country, and mandatory-field checks. |
| **Government Identity Validation** | Provider-abstracted mock validation against government records. |
| **Identity Verification** | Consolidates all prior scores into a final identity confidence score. |
| **Final Report Generation** | Builds structured KYC report; persists to `kyc_final_reports`. |
| **Decision** | Applies thresholds → APPROVED / REJECTED / MANUAL_REVIEW; updates DB. |

---

## Admin Workflow

1. Open the Admin Submissions list and click **Review** on any case.
2. On the Case Detail page, click **Run ID & Verification**.
3. The five admin-review stages run sequentially; the workflow panel updates live.
4. Inspect the generated final report (structured or raw JSON view).
5. Choose **Approve**, **Reject**, or **Manual Review** with optional admin notes.
6. All actions are recorded in the case timeline and audit trail.

---

## API Overview

Full reference: [docs/API.md](docs/API.md)

| Category | Key Endpoints |
|----------|--------------|
| Auth | `POST /api/v1/auth/register`, `/login`, `/refresh`, `/logout` |
| KYC | `POST /api/v1/kyc/submit`, `GET /api/v1/kyc/submissions` |
| Documents | `POST /api/v1/documents/upload` |
| Admin (existing) | `GET /api/v1/admin/kyc/submissions`, `POST .../override` |
| Admin Workflow | `POST /api/v1/admin/workflow/{id}/start`, `GET .../status`, `GET .../report` |
| Admin Decisions | `POST /api/v1/admin/workflow/{id}/approve`, `.../reject`, `.../manual-review` |
| System | `GET /health` |

---

## Testing

```bash
cd backend

# Run all tests
pytest tests/ -v --asyncio-mode=auto

# Run with coverage report
pytest tests/ -v --cov=app --cov-report=html --asyncio-mode=auto
# Open htmlcov/index.html

# Run a specific module
pytest tests/test_admin_workflow.py -v

# Run a specific test
pytest tests/test_admin_workflow.py::TestCustomerDocumentAnalysisAgent -v
```

Test modules:

| File | Coverage |
|------|---------|
| `tests/test_auth.py` | Auth endpoints (register, login, refresh, logout) |
| `tests/test_kyc.py` | KYC submission endpoints and pagination |
| `tests/test_agents.py` | Core agent nodes and full graph integration |
| `tests/test_fraud_detection.py` | Fraud detection utilities |
| `tests/test_admin_workflow.py` | All 5 new agents, graph transitions, workflow service helpers |

---

## Building the Desktop Application

### PyInstaller (.exe / Linux binary)

**Windows:**

```batch
cd desktop\pyinstaller
build_exe.bat
# Output: desktop\pyinstaller\dist\KYCPlatform\KYCPlatform.exe
```

**Linux / macOS:**

```bash
cd desktop/pyinstaller
chmod +x build_exe.sh
./build_exe.sh
# Output: desktop/pyinstaller/dist/KYCPlatform/KYCPlatform
```

### Electron (NSIS installer / AppImage / DMG)

**Windows:**

```batch
cd desktop\electron
build_electron.bat
# Output: desktop\electron\dist\KYC Platform Setup x.x.x.exe
```

**Linux / macOS (manual):**

```bash
cd frontend && npm run build   # Step 1: build React
cd ../desktop/electron
npm install
npm run build                  # Step 2: package with electron-builder
```

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Follow code style: Black formatter, isort, flake8, strict type hints
4. Write tests for new features (aim for >80% coverage)
5. Run the test suite: `pytest tests/ -v --asyncio-mode=auto`
6. Submit a pull request with a clear description

---

## Documentation

| Document | Description |
|----------|-------------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, component diagrams, full agent flow |
| [docs/API.md](docs/API.md) | Complete API reference with request/response examples |
| [docs/PODMAN_QUICKSTART.md](docs/PODMAN_QUICKSTART.md) | Running the platform with Podman |
| [backend/app/core/config.py](backend/app/core/config.py) | All environment variable settings |

---

## License

MIT License — see [LICENSE](LICENSE) for details.
