"""Initial schema – create all KYC application tables.

Revision ID: 001_initial_schema
Revises: (none)
Create Date: 2026-03-24

Creates:
  - users
  - kyc_submissions
  - documents
  - audit_logs

Plus all required PostgreSQL enum types.
"""

from __future__ import annotations

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON, UUID

from alembic import op

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------

revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Upgrade
# ---------------------------------------------------------------------------


def upgrade() -> None:
    """Create all tables from scratch."""

    bind = op.get_bind()

    # ------------------------------------------------------------------
    # Idempotency guard: if the users table already exists this migration
    # was applied successfully in a previous run — nothing to do.
    # ------------------------------------------------------------------
    if sa.inspect(bind).has_table("users"):
        return

    # ------------------------------------------------------------------
    # Partial-run recovery: if enum types were created in a previous
    # failed attempt but the tables were never committed, drop the orphan
    # types so we can recreate everything cleanly.
    # ------------------------------------------------------------------
    _partial_types = [
        "user_role_enum", "user_status_enum", "kyc_status_enum",
        "kyc_document_type_enum", "risk_level_enum", "document_type_enum",
        "document_status_enum", "audit_action_enum",
    ]
    for _t in _partial_types:
        op.execute(sa.text(f"DROP TYPE IF EXISTS {_t}"))

    # ------------------------------------------------------------------
    # users
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("phone_number", sa.String(20), nullable=True),
        sa.Column("date_of_birth", sa.DateTime(timezone=True), nullable=True),
        sa.Column("nationality", sa.String(3), nullable=True),
        sa.Column("address_line1", sa.String(255), nullable=True),
        sa.Column("address_line2", sa.String(255), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("state_province", sa.String(100), nullable=True),
        sa.Column("postal_code", sa.String(20), nullable=True),
        sa.Column("country", sa.String(3), nullable=True),
        sa.Column(
            "role",
            sa.Enum(
                "admin", "reviewer", "customer", "analyst",
                name="user_role_enum",
            ),
            nullable=False,
            server_default="customer",
        ),
        sa.Column(
            "status",
            sa.Enum(
                "active", "inactive", "suspended", "pending_verify", "locked",
                name="user_status_enum",
            ),
            nullable=False,
            server_default="pending_verify",
        ),
        sa.Column("is_email_verified", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("email_verification_token", sa.String(255), nullable=True),
        sa.Column("password_reset_token", sa.String(255), nullable=True),
        sa.Column("password_reset_expires", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_login_attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_ip", sa.String(45), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
    )
    op.create_unique_constraint("uq_users_email", "users", ["email"])
    op.create_unique_constraint("uq_users_username", "users", ["username"])
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_role", "users", ["role"])
    op.create_index("ix_users_status", "users", ["status"])
    op.create_index("ix_users_created_at", "users", ["created_at"])

    # ------------------------------------------------------------------
    # kyc_submissions
    # ------------------------------------------------------------------
    op.create_table(
        "kyc_submissions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("reference_number", sa.String(50), nullable=False, unique=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "reviewer_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("applicant_first_name", sa.String(100), nullable=False),
        sa.Column("applicant_last_name", sa.String(100), nullable=False),
        sa.Column("applicant_date_of_birth", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applicant_nationality", sa.String(3), nullable=True),
        sa.Column("applicant_address", sa.Text, nullable=True),
        sa.Column("applicant_phone", sa.String(20), nullable=True),
        sa.Column("applicant_email", sa.String(255), nullable=True),
        sa.Column(
            "primary_document_type",
            sa.Enum(
                "passport", "national_id", "drivers_license", "residence_permit",
                "utility_bill", "bank_statement", "tax_document", "selfie",
                name="kyc_document_type_enum",
            ),
            nullable=False,
        ),
        sa.Column("primary_document_number", sa.String(100), nullable=True),
        sa.Column("primary_document_issuing_country", sa.String(3), nullable=True),
        sa.Column("primary_document_expiry", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "draft", "submitted", "processing", "under_review",
                "approved", "rejected", "expired", "cancelled",
                name="kyc_status_enum",
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("status_reason", sa.Text, nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ai_confidence_score", sa.Float, nullable=True),
        sa.Column("ai_document_authenticity_score", sa.Float, nullable=True),
        sa.Column("ai_face_match_score", sa.Float, nullable=True),
        sa.Column("ai_liveness_score", sa.Float, nullable=True),
        sa.Column("ai_fraud_risk_score", sa.Float, nullable=True),
        sa.Column("ai_extracted_data", JSON, nullable=True),
        sa.Column("ai_verification_details", JSON, nullable=True),
        sa.Column("ai_flags", JSON, nullable=True),
        sa.Column(
            "risk_level",
            sa.Enum(
                "low", "medium", "high", "very_high",
                name="risk_level_enum",
            ),
            nullable=True,
        ),
        sa.Column("risk_factors", JSON, nullable=True),
        sa.Column("pep_check_result", sa.Boolean, nullable=True),
        sa.Column("sanctions_check_result", sa.Boolean, nullable=True),
        sa.Column("adverse_media_check_result", sa.Boolean, nullable=True),
        sa.Column("reviewer_notes", sa.Text, nullable=True),
        sa.Column("rejection_reasons", JSON, nullable=True),
        sa.Column("additional_info_requested", sa.Text, nullable=True),
        sa.Column("celery_task_id", sa.String(255), nullable=True),
        sa.Column("processing_attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("processing_error", sa.Text, nullable=True),
        sa.Column("langgraph_state", JSON, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_kyc_user_id", "kyc_submissions", ["user_id"])
    op.create_index("ix_kyc_status", "kyc_submissions", ["status"])
    op.create_index("ix_kyc_risk_level", "kyc_submissions", ["risk_level"])
    op.create_index("ix_kyc_created_at", "kyc_submissions", ["created_at"])
    op.create_index("ix_kyc_reviewer_id", "kyc_submissions", ["reviewer_id"])
    op.create_index("ix_kyc_reference_number", "kyc_submissions", ["reference_number"])

    # ------------------------------------------------------------------
    # documents
    # ------------------------------------------------------------------
    op.create_table(
        "documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column(
            "kyc_submission_id",
            UUID(as_uuid=True),
            sa.ForeignKey("kyc_submissions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_type",
            sa.Enum(
                "passport", "national_id_front", "national_id_back",
                "drivers_license_front", "drivers_license_back",
                "residence_permit", "utility_bill", "bank_statement",
                "tax_document", "selfie_photo", "selfie_with_document", "other",
                name="document_type_enum",
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "processing", "processed", "verified", "rejected", "error",
                name="document_status_enum",
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("stored_filename", sa.String(255), nullable=False),
        sa.Column("storage_path", sa.String(500), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger, nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("file_hash_sha256", sa.String(64), nullable=False),
        sa.Column("is_encrypted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("image_width", sa.Integer, nullable=True),
        sa.Column("image_height", sa.Integer, nullable=True),
        sa.Column("image_dpi", sa.Integer, nullable=True),
        sa.Column("ocr_raw_text", sa.Text, nullable=True),
        sa.Column("ocr_structured_data", JSON, nullable=True),
        sa.Column("ocr_confidence", sa.Float, nullable=True),
        sa.Column("ocr_language_detected", sa.String(10), nullable=True),
        sa.Column("ocr_processing_time_ms", sa.Integer, nullable=True),
        sa.Column("ai_authenticity_score", sa.Float, nullable=True),
        sa.Column("ai_tamper_detected", sa.Boolean, nullable=True),
        sa.Column("ai_document_expired", sa.Boolean, nullable=True),
        sa.Column("ai_verification_notes", sa.Text, nullable=True),
        sa.Column("ai_extracted_fields", JSON, nullable=True),
        sa.Column("ai_analysis_metadata", JSON, nullable=True),
        sa.Column("processing_error", sa.Text, nullable=True),
        sa.Column("processing_attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_documents_kyc_submission_id", "documents", ["kyc_submission_id"]
    )
    op.create_index("ix_documents_document_type", "documents", ["document_type"])
    op.create_index("ix_documents_status", "documents", ["status"])
    op.create_index("ix_documents_created_at", "documents", ["created_at"])

    # ------------------------------------------------------------------
    # audit_logs
    # ------------------------------------------------------------------
    op.create_table(
        "audit_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "kyc_submission_id",
            UUID(as_uuid=True),
            sa.ForeignKey("kyc_submissions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "action",
            sa.Enum(
                "create", "read", "update", "delete",
                "login", "logout", "password_change",
                "kyc_submit", "kyc_approve", "kyc_reject", "kyc_override",
                "document_upload",
                name="audit_action_enum",
            ),
            nullable=False,
        ),
        sa.Column("resource_type", sa.String(100), nullable=True),
        sa.Column("resource_id", sa.String(255), nullable=True),
        sa.Column("details", JSON, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("request_id", sa.String(100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_audit_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_kyc_id", "audit_logs", ["kyc_submission_id"])
    op.create_index("ix_audit_action", "audit_logs", ["action"])
    op.create_index("ix_audit_created_at", "audit_logs", ["created_at"])

    # ------------------------------------------------------------------
    # Trigger: auto-update updated_at on users
    # ------------------------------------------------------------------
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)

    for table_name in ("users", "kyc_submissions", "documents"):
        op.execute(f"""
            CREATE TRIGGER update_{table_name}_updated_at
            BEFORE UPDATE ON {table_name}
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
        """)


# ---------------------------------------------------------------------------
# Downgrade
# ---------------------------------------------------------------------------


def downgrade() -> None:
    """Drop all tables and enum types created in upgrade()."""

    # Drop triggers
    for table_name in ("users", "kyc_submissions", "documents"):
        op.execute(f"DROP TRIGGER IF EXISTS update_{table_name}_updated_at ON {table_name};")

    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column();")

    # Drop tables (reverse dependency order)
    op.drop_table("audit_logs")
    op.drop_table("documents")
    op.drop_table("kyc_submissions")
    op.drop_table("users")

    # Drop enum types
    for enum_name in [
        "audit_action_enum",
        "document_status_enum",
        "document_type_enum",
        "risk_level_enum",
        "kyc_document_type_enum",
        "kyc_status_enum",
        "user_status_enum",
        "user_role_enum",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name};")
