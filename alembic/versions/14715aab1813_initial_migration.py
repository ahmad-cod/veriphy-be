"""initial_migration

Revision ID: 14715aab1813
Revises: 
Create Date: 2026-05-15 04:36:33.203568

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '14715aab1813'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create PostgreSQL enum types first so tables can reference them.
    kyc_status_enum = postgresql.ENUM(
        "pending",
        "verified",
        "rejected",
        "flagged",
        name="kyc_status_enum",
        create_type=False,
    )
    job_state_enum = postgresql.ENUM(
        "received",
        "processing_ai",
        "processing_ledger",
        "awaiting_squad",
        "resolved_verified",
        "resolved_fake",
        "resolved_timeout",
        name="job_state_enum",
        create_type=False,
    )
    transaction_status_enum = postgresql.ENUM(
        "success",
        "failed",
        "pending",
        name="transaction_status_enum",
        create_type=False,
    )
    actor_type_enum = postgresql.ENUM(
        "system",
        "merchant",
        "admin",
        name="actor_type_enum",
        create_type=False,
    )

    kyc_status_enum.create(op.get_bind(), checkfirst=True)
    job_state_enum.create(op.get_bind(), checkfirst=True)
    transaction_status_enum.create(op.get_bind(), checkfirst=True)
    actor_type_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "merchants",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("phone", sa.String(length=30), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("bvn_encrypted", sa.String(), nullable=False),
        sa.Column("bvn_hash", sa.String(), nullable=False),
        sa.Column("squad_account", sa.String(length=20), nullable=True),
        sa.Column("squad_bank_code", sa.String(length=10), nullable=True),
        sa.Column("kyc_status", kyc_status_enum, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_merchants_phone_active",
        "merchants",
        ["phone"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_merchants_bvn_active",
        "merchants",
        ["bvn_hash"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "verification_jobs",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("merchant_id", sa.UUID(as_uuid=True), sa.ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sms_content_encrypted", sa.String(), nullable=False),
        sa.Column("sms_hash", sa.String(), nullable=False, unique=True),
        sa.Column("extracted_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("extracted_sender", sa.String(length=255), nullable=True),
        sa.Column("extracted_transaction_ref", sa.String(length=100), nullable=True),
        sa.Column("state", job_state_enum, nullable=False),
        sa.Column("resolution_reason", sa.String(length=100), nullable=True),
        sa.Column("squad_txn_ref", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_verification_jobs_merchant_state_date", "verification_jobs", ["merchant_id", "state", "created_at"])
    op.create_index("ix_verification_jobs_merchant_id", "verification_jobs", ["merchant_id"])
    op.create_index("ix_verification_jobs_sms_hash", "verification_jobs", ["sms_hash"], unique=True)
    op.create_index("ix_verification_jobs_extracted_transaction_ref", "verification_jobs", ["extracted_transaction_ref"])
    op.create_index("ix_verification_jobs_state", "verification_jobs", ["state"])
    op.create_index("ix_verification_jobs_squad_txn_ref", "verification_jobs", ["squad_txn_ref"])
    op.create_index("ix_verification_jobs_created_at", "verification_jobs", ["created_at"])

    op.create_table(
        "ledger_transactions",
        sa.Column("txn_ref", sa.String(length=100), primary_key=True),
        sa.Column("merchant_id", sa.UUID(as_uuid=True), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("job_id", sa.UUID(as_uuid=True), sa.ForeignKey("verification_jobs.id"), nullable=True),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("status", transaction_status_enum, nullable=False),
        sa.Column("settled_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_ledger_transactions_merchant_id", "ledger_transactions", ["merchant_id"])
    op.create_index("ix_ledger_transactions_job_id", "ledger_transactions", ["job_id"])

    op.create_table(
        "verification_images",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", sa.UUID(as_uuid=True), sa.ForeignKey("verification_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("s3_key", sa.String(length=255), nullable=False, unique=True),
        sa.Column("p_hash", sa.String(length=64), nullable=False),
        sa.Column("vision_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("job_id", "p_hash", name="uq_image_job_phash"),
    )
    op.create_index("ix_verification_images_job_id", "verification_images", ["job_id"])
    op.create_index("ix_verification_images_p_hash", "verification_images", ["p_hash"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("actor_type", actor_type_enum, nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("changes", sa.JSON(), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("correlation_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_audit_logs_entity_type", "audit_logs", ["entity_type"])
    op.create_index("ix_audit_logs_entity_id", "audit_logs", ["entity_id"])
    op.create_index("ix_audit_logs_correlation_id", "audit_logs", ["correlation_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_audit_logs_correlation_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_entity_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_entity_type", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_verification_images_p_hash", table_name="verification_images")
    op.drop_index("ix_verification_images_job_id", table_name="verification_images")
    op.drop_table("verification_images")

    op.drop_index("ix_ledger_transactions_job_id", table_name="ledger_transactions")
    op.drop_index("ix_ledger_transactions_merchant_id", table_name="ledger_transactions")
    op.drop_table("ledger_transactions")

    op.drop_index("ix_verification_jobs_created_at", table_name="verification_jobs")
    op.drop_index("ix_verification_jobs_squad_txn_ref", table_name="verification_jobs")
    op.drop_index("ix_verification_jobs_state", table_name="verification_jobs")
    op.drop_index("ix_verification_jobs_extracted_transaction_ref", table_name="verification_jobs")
    op.drop_index("ix_verification_jobs_sms_hash", table_name="verification_jobs")
    op.drop_index("ix_verification_jobs_merchant_id", table_name="verification_jobs")
    op.drop_index("ix_verification_jobs_merchant_state_date", table_name="verification_jobs")
    op.drop_table("verification_jobs")

    op.drop_index("ix_merchants_bvn_active", table_name="merchants")
    op.drop_index("ix_merchants_phone_active", table_name="merchants")
    op.drop_table("merchants")

    actor_type_enum = sa.Enum(name="actor_type_enum")
    transaction_status_enum = sa.Enum(name="transaction_status_enum")
    job_state_enum = sa.Enum(name="job_state_enum")
    kyc_status_enum = sa.Enum(name="kyc_status_enum")

    actor_type_enum.drop(op.get_bind(), checkfirst=True)
    transaction_status_enum.drop(op.get_bind(), checkfirst=True)
    job_state_enum.drop(op.get_bind(), checkfirst=True)
    kyc_status_enum.drop(op.get_bind(), checkfirst=True)
