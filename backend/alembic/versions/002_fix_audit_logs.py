"""Fix audit_logs table schema to match ORM model.

Revision ID: 002_fix_audit_logs
Revises: 001
Create Date: 2026-03-25
"""

from __future__ import annotations

from alembic import op

# revision identifiers
revision = "002_fix_audit_logs"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop old audit_logs table and its enum (they have wrong schema)
    op.execute("DROP TABLE IF EXISTS audit_logs CASCADE")
    op.execute("DROP TYPE IF EXISTS audit_action_enum CASCADE")

    # Recreate enum with correct values matching AuditAction ORM model
    op.execute("""
        CREATE TYPE audit_action_enum AS ENUM (
            'user_registered', 'user_login', 'user_login_failed', 'user_logout',
            'user_updated', 'user_password_changed', 'user_password_reset_requested',
            'user_password_reset', 'user_email_verified', 'user_activated',
            'user_deactivated', 'user_suspended', 'user_locked', 'user_deleted',
            'user_role_changed',
            'kyc_created', 'kyc_submitted', 'kyc_processing_started',
            'kyc_processing_completed', 'kyc_processing_failed', 'kyc_under_review',
            'kyc_approved', 'kyc_rejected', 'kyc_cancelled', 'kyc_expired',
            'kyc_resubmitted', 'kyc_viewed', 'kyc_status_changed',
            'document_uploaded', 'document_processed', 'document_verified',
            'document_rejected', 'document_downloaded', 'document_deleted',
            'admin_user_list_viewed', 'admin_kyc_list_viewed', 'admin_stats_viewed',
            'admin_bulk_action',
            'system_startup', 'system_shutdown', 'system_error'
        )
    """)

    # Recreate audit_logs with correct schema using raw SQL to avoid
    # SQLAlchemy trying to auto-create the enum type we already created above
    op.execute("""
        CREATE TABLE audit_logs (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id     UUID REFERENCES users(id) ON DELETE SET NULL,
            user_email  VARCHAR(255),
            user_role   VARCHAR(50),
            action      audit_action_enum NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            entity_type VARCHAR(100),
            entity_id   VARCHAR(255),
            kyc_submission_id UUID REFERENCES kyc_submissions(id) ON DELETE SET NULL,
            ip_address  VARCHAR(45),
            user_agent  VARCHAR(500),
            request_id  VARCHAR(100),
            session_id  VARCHAR(100),
            old_values  JSON,
            new_values  JSON,
            extra_data  JSON,
            success     BOOLEAN NOT NULL DEFAULT TRUE,
            error_message TEXT,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("CREATE INDEX ix_audit_user_id           ON audit_logs (user_id)")
    op.execute("CREATE INDEX ix_audit_kyc_submission_id ON audit_logs (kyc_submission_id)")
    op.execute("CREATE INDEX ix_audit_action            ON audit_logs (action)")
    op.execute("CREATE INDEX ix_audit_created_at        ON audit_logs (created_at)")
    op.execute("CREATE INDEX ix_audit_entity_type       ON audit_logs (entity_type)")
    op.execute("CREATE INDEX ix_audit_entity_id         ON audit_logs (entity_id)")
    op.execute("CREATE INDEX ix_audit_ip_address        ON audit_logs (ip_address)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS audit_logs CASCADE")
    op.execute("DROP TYPE IF EXISTS audit_action_enum CASCADE")
