"""
pytest Configuration and Fixtures

Provides shared fixtures for:
  - async_client: AsyncClient for FastAPI testing
  - test_db: SQLite in-memory async test database
  - test_user / test_admin: pre-created DB users
  - auth_headers / admin_headers: Bearer JWT headers
  - mock_ocr: patches EasyOCR to return fake text
  - mock_redis: patches Redis client
  - sample_kyc_data: valid KYC form payload dict
  - sample_document: creates a test Document record
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator, Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# ---------------------------------------------------------------------------
# Override settings BEFORE any app imports so the test DB URL is used
# ---------------------------------------------------------------------------
import os
os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-chars-long!!")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-minimum-32-chars!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("DEBUG", "true")

from app.core.config import settings  # noqa: E402
from app.core.database import Base  # noqa: E402
from app.core.security import create_access_token, hash_password  # noqa: E402
from app.models.user import User, UserRole, UserStatus  # noqa: E402
from app.models.kyc import KYCSubmission, KYCStatus, KYCDocumentType  # noqa: E402
from app.models.document import Document, DocumentType, DocumentStatus  # noqa: E402
from main import create_application  # noqa: E402


# ---------------------------------------------------------------------------
# SQLite in-memory engine (per test session)
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)

# Enable WAL mode and foreign keys for SQLite
@event.listens_for(test_engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


TestAsyncSession = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="session")
async def test_db_engine():
    """Create test tables once per session."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield test_engine
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture()
async def test_db(test_db_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Provide a transactional test database session.
    Each test runs in a transaction that is rolled back on teardown.
    """
    async with TestAsyncSession() as session:
        try:
            yield session
        finally:
            await session.rollback()
            await session.close()


# ---------------------------------------------------------------------------
# User fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture()
async def test_user(test_db: AsyncSession) -> User:
    """Create and persist a regular customer user."""
    user = User(
        id=uuid.uuid4(),
        email="testuser@kyc-test.com",
        username="testuser",
        hashed_password=hash_password("TestPass1!"),
        first_name="Test",
        last_name="User",
        role=UserRole.CUSTOMER,
        status=UserStatus.ACTIVE,
        is_email_verified=True,
    )
    test_db.add(user)
    await test_db.flush()
    return user


@pytest_asyncio.fixture()
async def test_admin(test_db: AsyncSession) -> User:
    """Create and persist an admin user."""
    admin = User(
        id=uuid.uuid4(),
        email="admin@kyc-test.com",
        username="adminuser",
        hashed_password=hash_password("AdminPass1!"),
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMIN,
        status=UserStatus.ACTIVE,
        is_email_verified=True,
    )
    test_db.add(admin)
    await test_db.flush()
    return admin


# ---------------------------------------------------------------------------
# Auth header fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def auth_headers(test_user: User) -> Dict[str, str]:
    """Return Bearer headers for test_user."""
    token = create_access_token(
        subject=str(test_user.id),
        additional_claims={"role": test_user.role.value},
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def admin_headers(test_admin: User) -> Dict[str, str]:
    """Return Bearer headers for test_admin."""
    token = create_access_token(
        subject=str(test_admin.id),
        additional_claims={"role": test_admin.role.value},
    )
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Mock fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_redis():
    """
    Mock Redis client so tests do not require a running Redis instance.
    Stubs: ping, set, get, delete, is_token_revoked, revoke_token.
    """
    with patch("app.core.redis_client.redis_client") as mock_client:
        mock_client.ping = AsyncMock(return_value=True)
        mock_client.set = AsyncMock(return_value=True)
        mock_client.get = AsyncMock(return_value=None)
        mock_client.delete = AsyncMock(return_value=1)
        mock_client.is_token_revoked = AsyncMock(return_value=False)
        mock_client.revoke_token = AsyncMock(return_value=True)
        mock_client.close = AsyncMock(return_value=None)
        yield mock_client


@pytest.fixture()
def mock_ocr():
    """
    Mock EasyOCR reader to return deterministic fake text.
    Returns a list of (bbox, text, confidence) tuples mimicking EasyOCR output.
    """
    fake_results = [
        ([[0, 0], [100, 0], [100, 20], [0, 20]], "JOHN DOE", 0.95),
        ([[0, 25], [100, 25], [100, 45], [0, 45]], "DOB: 1990-01-15", 0.92),
        ([[0, 50], [100, 50], [100, 70], [0, 70]], "ID: AB123456", 0.90),
        ([[0, 75], [100, 75], [100, 95], [0, 95]], "EXP: 2030-01-15", 0.88),
    ]

    with patch("easyocr.Reader") as mock_reader_cls:
        mock_reader = MagicMock()
        mock_reader.readtext.return_value = fake_results
        mock_reader_cls.return_value = mock_reader
        yield mock_reader


# ---------------------------------------------------------------------------
# Sample data fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_kyc_data() -> Dict[str, Any]:
    """Return a valid KYC form data dictionary."""
    return {
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
        "primary_document_expiry": "2030-01-15",
    }


@pytest.fixture()
def sample_agent_form_data() -> Dict[str, Any]:
    """Return form_data as expected by agent nodes (snake_case flat dict)."""
    return {
        "first_name": "John",
        "last_name": "Doe",
        "date_of_birth": "1990-01-15",
        "id_type": "passport",
        "id_number": "AB123456",
        "nationality": "USA",
        "address": "123 Main St, Springfield, IL 62701",
        "phone": "+15555550100",
        "email": "john.doe@example.com",
    }


@pytest_asyncio.fixture()
async def sample_document(test_db: AsyncSession, test_user: User) -> Document:
    """
    Create a minimal KYCSubmission + linked Document record for tests that
    need a real document ID in the database.
    """
    # Create a KYC submission first (Document has an FK to it)
    submission = KYCSubmission(
        id=uuid.uuid4(),
        reference_number=f"KYC-TEST-{uuid.uuid4().hex[:8].upper()}",
        user_id=test_user.id,
        applicant_first_name="John",
        applicant_last_name="Doe",
        primary_document_type=KYCDocumentType.PASSPORT,
        status=KYCStatus.SUBMITTED,
    )
    test_db.add(submission)
    await test_db.flush()

    doc = Document(
        id=uuid.uuid4(),
        kyc_submission_id=submission.id,
        document_type=DocumentType.PASSPORT,
        status=DocumentStatus.PENDING,
        original_filename="passport.jpg",
        stored_filename=f"{uuid.uuid4().hex}.jpg",
        storage_path=f"uploads/test/{uuid.uuid4().hex}.jpg",
        file_size_bytes=102400,
        mime_type="image/jpeg",
        file_hash_sha256="a" * 64,
    )
    test_db.add(doc)
    await test_db.flush()
    return doc


# ---------------------------------------------------------------------------
# FastAPI test client
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture()
async def async_client(test_db: AsyncSession, mock_redis) -> AsyncGenerator[AsyncClient, None]:
    """
    AsyncClient connected to the FastAPI app.
    Overrides the database dependency to use the in-memory test DB.
    """
    from app.core.database import get_db  # noqa: PLC0415

    app = create_application()

    # Override get_db to use test session
    async def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client

    app.dependency_overrides.clear()
