#!/usr/bin/env python3
"""
Seed demo users for the KYC Platform.

Creates two demo accounts:
  - admin@kyc.com   / Admin@KYC2024!   (role: admin)
  - user@kyc.com    / User@KYC2024!    (role: customer)

Safe to run multiple times (skips existing users).

Usage (from inside the backend container or with PYTHONPATH=backend):
    python seed_demo_users.py
"""

from __future__ import annotations

import asyncio
import os
import sys

# Allow running from the backend directory
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
# Import the full models package so all mappers (including workflow models
# referenced by KYCSubmission relationships) are registered before any query.
import app.models  # noqa: F401
from app.models.user import User, UserRole, UserStatus


DEMO_USERS = [
    {
        "email": "admin@kyc.com",
        "username": "admin_kyc",
        "first_name": "Admin",
        "last_name": "User",
        "password": "Admin@KYC2024!",
        "role": UserRole.ADMIN,
    },
    {
        "email": "user@kyc.com",
        "username": "demo_user",
        "first_name": "Demo",
        "last_name": "User",
        "password": "User@KYC2024!",
        "role": UserRole.CUSTOMER,
    },
]


async def seed(session: AsyncSession) -> None:
    for u in DEMO_USERS:
        result = await session.execute(select(User).where(User.email == u["email"]))
        existing = result.scalar_one_or_none()
        if existing:
            print(f"  [skip] {u['email']} already exists")
            continue

        user = User(
            email=u["email"],
            username=u["username"],
            first_name=u["first_name"],
            last_name=u["last_name"],
            hashed_password=hash_password(u["password"]),
            role=u["role"],
            status=UserStatus.ACTIVE,
            is_email_verified=True,
            failed_login_attempts=0,
        )
        session.add(user)
        print(f"  [created] {u['email']}  role={u['role'].value}")

    await session.commit()


async def main() -> None:
    print("Seeding demo users...")
    async with AsyncSessionLocal() as session:
        await seed(session)
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
