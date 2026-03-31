"""Admin workflow tables – KYCWorkflowStep, KYCFinalReport, KYCAdminDecision, KYCTimeline.

Revision ID: 004_admin_workflow
Revises: 003_extend_nationality
Create Date: 2026-03-27

Creates:
  - kyc_workflow_steps
  - kyc_final_reports
  - kyc_admin_decisions
  - kyc_timeline

Plus the new PostgreSQL enum types used by these tables.

NOTE: All DDL is written as raw SQL via op.execute() with IF NOT EXISTS guards.
This avoids SQLAlchemy 2.x + asyncpg losing create_type=False during dialect
adaptation, which would cause DuplicateObjectError on retry after a partial run.
"""

from __future__ import annotations

from typing import Union

from alembic import op

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------

revision: str = "004_admin_workflow"
down_revision: Union[str, None] = "003_extend_nationality"
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# Enum type names
# ---------------------------------------------------------------------------

ENUM_STEP_NAME = "workflow_step_name_enum"
ENUM_STEP_STATUS = "workflow_step_status_enum"
ENUM_DECISION_TYPE = "admin_decision_type_enum"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_enum(name: str, values: list[str]) -> None:
    """Create a PostgreSQL enum type, silently skip if it already exists."""
    values_sql = ", ".join(f"'{v}'" for v in values)
    op.execute(
        f"DO $$ BEGIN "
        f"  CREATE TYPE {name} AS ENUM ({values_sql}); "
        f"EXCEPTION WHEN duplicate_object THEN null; "
        f"END $$;"
    )


def _drop_enum(name: str) -> None:
    op.execute(f"DROP TYPE IF EXISTS {name};")


# ---------------------------------------------------------------------------
# Upgrade
# ---------------------------------------------------------------------------


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Enum types (idempotent — duplicate_object is silently ignored)
    # ------------------------------------------------------------------
    _create_enum(ENUM_STEP_NAME, [
        "ingestion",
        "document_processing",
        "customer_document_analysis",
        "customer_compliance_review",
        "government_identity_validation",
        "identity_verification",
        "final_report_generation",
        "decision",
    ])
    _create_enum(ENUM_STEP_STATUS, [
        "pending",
        "in_progress",
        "completed",
        "failed",
        "skipped",
    ])
    _create_enum(ENUM_DECISION_TYPE, [
        "approved",
        "rejected",
        "manual_review",
    ])

    # ------------------------------------------------------------------
    # 2. kyc_workflow_steps
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS kyc_workflow_steps (
            id              UUID PRIMARY KEY,
            submission_id   UUID NOT NULL
                                REFERENCES kyc_submissions(id) ON DELETE CASCADE,
            step_name       workflow_step_name_enum NOT NULL,
            step_order      INTEGER NOT NULL,
            status          workflow_step_status_enum NOT NULL DEFAULT 'pending',
            summary         TEXT,
            details         JSON,
            score           DOUBLE PRECISION,
            error_message   TEXT,
            started_at      TIMESTAMPTZ,
            completed_at    TIMESTAMPTZ,
            duration_ms     INTEGER,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_wfstep_submission_id ON kyc_workflow_steps(submission_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_wfstep_step_name    ON kyc_workflow_steps(step_name)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_wfstep_status       ON kyc_workflow_steps(status)")

    # ------------------------------------------------------------------
    # 3. kyc_final_reports
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS kyc_final_reports (
            id                      UUID PRIMARY KEY,
            submission_id           UUID NOT NULL UNIQUE
                                        REFERENCES kyc_submissions(id) ON DELETE CASCADE,
            report_data             JSON,
            final_confidence_score  DOUBLE PRECISION,
            recommended_action      VARCHAR(50),
            fraud_detected          BOOLEAN NOT NULL DEFAULT FALSE,
            compliance_passed       BOOLEAN NOT NULL DEFAULT FALSE,
            government_validated    BOOLEAN NOT NULL DEFAULT FALSE,
            identity_verified       BOOLEAN NOT NULL DEFAULT FALSE,
            document_quality_score  DOUBLE PRECISION,
            document_tampered       BOOLEAN NOT NULL DEFAULT FALSE,
            generated_at            TIMESTAMPTZ,
            created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_finalreport_submission_id ON kyc_final_reports(submission_id)")

    # ------------------------------------------------------------------
    # 4. kyc_admin_decisions
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS kyc_admin_decisions (
            id              UUID PRIMARY KEY,
            submission_id   UUID NOT NULL
                                REFERENCES kyc_submissions(id) ON DELETE CASCADE,
            admin_id        UUID
                                REFERENCES users(id) ON DELETE SET NULL,
            decision_type   admin_decision_type_enum NOT NULL,
            notes           TEXT,
            decided_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_admindecision_submission_id ON kyc_admin_decisions(submission_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_admindecision_admin_id      ON kyc_admin_decisions(admin_id)")

    # ------------------------------------------------------------------
    # 5. kyc_timeline
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS kyc_timeline (
            id              UUID PRIMARY KEY,
            submission_id   UUID NOT NULL
                                REFERENCES kyc_submissions(id) ON DELETE CASCADE,
            event_type      VARCHAR(100) NOT NULL,
            event_title     VARCHAR(255) NOT NULL,
            event_detail    TEXT,
            actor           VARCHAR(100),
            metadata        JSON,
            occurred_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_timeline_submission_id ON kyc_timeline(submission_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_timeline_occurred_at   ON kyc_timeline(occurred_at)")


# ---------------------------------------------------------------------------
# Downgrade
# ---------------------------------------------------------------------------


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS kyc_timeline")
    op.execute("DROP TABLE IF EXISTS kyc_admin_decisions")
    op.execute("DROP TABLE IF EXISTS kyc_final_reports")
    op.execute("DROP TABLE IF EXISTS kyc_workflow_steps")
    _drop_enum(ENUM_DECISION_TYPE)
    _drop_enum(ENUM_STEP_STATUS)
    _drop_enum(ENUM_STEP_NAME)
