"""Extend nationality column from VARCHAR(3) to VARCHAR(100).

Revision ID: 003_extend_nationality
Revises: 002_fix_audit_logs
Create Date: 2026-03-26
"""

from __future__ import annotations

from alembic import op


revision = "003_extend_nationality"
down_revision = "002_fix_audit_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # kyc_submissions.applicant_nationality was VARCHAR(3) — extend to 100
    op.execute(
        "ALTER TABLE kyc_submissions ALTER COLUMN applicant_nationality TYPE VARCHAR(100)"
    )
    # users.nationality is also VARCHAR(3) — extend it too
    op.execute(
        "ALTER TABLE users ALTER COLUMN nationality TYPE VARCHAR(100)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE kyc_submissions ALTER COLUMN applicant_nationality TYPE VARCHAR(3)"
    )
    op.execute(
        "ALTER TABLE users ALTER COLUMN nationality TYPE VARCHAR(3)"
    )
