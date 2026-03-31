"""
Tests for Authentication Endpoints

Covers:
  POST /api/v1/auth/register
  POST /api/v1/auth/login
  POST /api/v1/auth/refresh
  POST /api/v1/auth/logout
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_refresh_token
from app.models.user import User


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_user_success(async_client: AsyncClient):
    """A new user can register with valid credentials."""
    payload = {
        "email": "newuser@kyc-test.com",
        "username": "newuser",
        "password": "StrongPass1!",
        "first_name": "New",
        "last_name": "User",
    }
    response = await async_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["email"] == payload["email"]
    assert data["username"] == payload["username"]
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_register_duplicate_email_fails(
    async_client: AsyncClient, test_user: User
):
    """Registering with an email already in use returns 409."""
    payload = {
        "email": test_user.email,
        "username": "anotheruser",
        "password": "StrongPass1!",
        "first_name": "Dup",
        "last_name": "User",
    }
    response = await async_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code in (400, 409), response.text


@pytest.mark.asyncio
async def test_register_weak_password_fails(async_client: AsyncClient):
    """Registration with a weak password is rejected."""
    payload = {
        "email": "weakpass@kyc-test.com",
        "username": "weakpassuser",
        "password": "short",
        "first_name": "Weak",
        "last_name": "Pass",
    }
    response = await async_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422, response.text


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_success(async_client: AsyncClient, test_user: User):
    """Valid credentials return access and refresh tokens."""
    payload = {"username": test_user.email, "password": "TestPass1!"}
    response = await async_client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0


@pytest.mark.asyncio
async def test_login_wrong_password(async_client: AsyncClient, test_user: User):
    """Wrong password returns 401."""
    payload = {"username": test_user.email, "password": "WrongPass99!"}
    response = await async_client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 401, response.text


@pytest.mark.asyncio
async def test_login_unknown_email_fails(async_client: AsyncClient):
    """Login with an email that does not exist returns 401 or 404."""
    payload = {"username": "ghost@example.com", "password": "SomePass1!"}
    response = await async_client.post("/api/v1/auth/login", json=payload)
    assert response.status_code in (401, 404), response.text


# ---------------------------------------------------------------------------
# Refresh token
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_token(async_client: AsyncClient, test_user: User):
    """A valid refresh token yields a new access token."""
    refresh_token = create_refresh_token(
        subject=str(test_user.id),
        additional_claims={"role": test_user.role.value},
    )
    response = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert "access_token" in data


@pytest.mark.asyncio
async def test_refresh_invalid_token_fails(async_client: AsyncClient):
    """An invalid refresh token returns 401."""
    response = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "not.a.valid.token"},
    )
    assert response.status_code == 401, response.text


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_logout_invalidates_token(
    async_client: AsyncClient,
    auth_headers: dict,
    mock_redis,
):
    """Logging out revokes the current token; subsequent requests fail."""
    # Logout
    response = await async_client.post("/api/v1/auth/logout", headers=auth_headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert "message" in data

    # Simulate token revoked: mock_redis.is_token_revoked now returns True
    mock_redis.is_token_revoked.return_value = True  # type: ignore[attr-defined]

    # Any protected endpoint should now return 401
    me_response = await async_client.get(
        "/api/v1/auth/me", headers=auth_headers
    )
    assert me_response.status_code in (401, 404), me_response.text
