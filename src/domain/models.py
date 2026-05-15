import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import Any, Optional
from decimal import Decimal

from sqlalchemy import Numeric, String, ForeignKey, Enum as SQLEnum, Float, Boolean, Index, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.base import Base

# --- ENUMS ---
class KycStatus(str, PyEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"
    FLAGGED = "flagged"

class JobState(str, PyEnum):
    RECEIVED = "received"
    PROCESSING_AI = "processing_ai"
    PROCESSING_LEDGER = "processing_ledger"
    AWAITING_SQUAD = "awaiting_squad"
    RESOLVED_VERIFIED = "resolved_verified"
    RESOLVED_FAKE = "resolved_fake"
    RESOLVED_TIMEOUT = "resolved_timeout"

class TransactionStatus(str, PyEnum):
    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"

class ActorType(str, PyEnum):
    SYSTEM = "system"
    MERCHANT = "merchant"
    ADMIN = "admin"


# --- MODELS ---
class Merchant(Base):
    __tablename__ = "merchants"
    __table_args__ = (
        Index(
            "ix_merchants_phone_active",
            "phone",
            unique=True,
            postgresql_where=text("deleted_at IS NULL")
        ),
        Index(
            "ix_merchants_bvn_active",
            "bvn_hash",
            unique=True,
            postgresql_where=text("deleted_at IS NULL")
        )
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone: Mapped[str] = mapped_column(String(30)) # Expanded to 30 for international
    
    # Soft Delete & Active State
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), default=True)
    
    # Shadow-PII Strategy
    bvn_encrypted: Mapped[str] = mapped_column(String, comment="Ciphertext via AWS KMS DEK")
    bvn_hash: Mapped[str] = mapped_column(String, comment="Argon2id + pepper for lookups")
    
    # Squad Integration Data
    squad_account: Mapped[Optional[str]] = mapped_column(String(20), index=True)
    squad_bank_code: Mapped[Optional[str]] = mapped_column(String(10))
    kyc_status: Mapped[KycStatus] = mapped_column(
        SQLEnum(
            KycStatus,
            name="kyc_status_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=KycStatus.PENDING,
    )
    
    # CRITICAL FIX: Server-side timestamps
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column()
    
    jobs: Mapped[list["VerificationJob"]] = relationship(back_populates="merchant", cascade="all, delete-orphan")


class VerificationJob(Base):
    __tablename__ = "verification_jobs"
    __table_args__ = (
        # Composite index for heavy dashboard queries
        Index("ix_verification_jobs_merchant_state_date", "merchant_id", "state", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    merchant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("merchants.id", ondelete="CASCADE"), index=True)
    
    # CRITICAL FIX: Encrypted Payload & Anti-Replay
    sms_content_encrypted: Mapped[str] = mapped_column(String, comment="KMS Encrypted raw SMS payload")
    sms_hash: Mapped[str] = mapped_column(String, unique=True, index=True, comment="SHA-256 of SMS to prevent duplicate processing")
    
    # Extracted Entities
    extracted_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    extracted_sender: Mapped[Optional[str]] = mapped_column(String(255))
    extracted_transaction_ref: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    
    # State Machine
    state: Mapped[JobState] = mapped_column(
        SQLEnum(
            JobState,
            name="job_state_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=JobState.RECEIVED,
        index=True,
    )
    resolution_reason: Mapped[Optional[str]] = mapped_column(String(100)) 
    squad_txn_ref: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
    resolved_at: Mapped[Optional[datetime]] = mapped_column() # Set explicitly when verdict is reached

    merchant: Mapped["Merchant"] = relationship(back_populates="jobs")
    images: Mapped[list["VerificationImage"]] = relationship(back_populates="job", cascade="all, delete-orphan")
    ledger_transactions: Mapped[list["LedgerTransaction"]] = relationship(back_populates="job")


class LedgerTransaction(Base):
    __tablename__ = "ledger_transactions"
    __table_args__ = {'comment': 'Local cache of Squad webhooks to handle out-of-order events'}

    txn_ref: Mapped[str] = mapped_column(String(100), primary_key=True)
    merchant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("merchants.id"), index=True)
    
    # Traceability link to the job that claimed this transaction
    job_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("verification_jobs.id"), index=True)
    
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    status: Mapped[TransactionStatus] = mapped_column(
        SQLEnum(
            TransactionStatus,
            name="transaction_status_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        )
    )
    settled_at: Mapped[datetime] = mapped_column()
    
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
    
    job: Mapped[Optional["VerificationJob"]] = relationship(back_populates="ledger_transactions")


class VerificationImage(Base):
    __tablename__ = "verification_images"
    __table_args__ = (
        UniqueConstraint("job_id", "p_hash", name="uq_image_job_phash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("verification_jobs.id", ondelete="CASCADE"), index=True)
    
    s3_key: Mapped[str] = mapped_column(String(255), unique=True)
    p_hash: Mapped[str] = mapped_column(String(64), index=True, comment="Perceptual hash for duplicate detection")
    vision_score: Mapped[Optional[float]] = mapped_column(Float)
    
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
    
    job: Mapped["VerificationJob"] = relationship(back_populates="images")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String(50), index=True) 
    
    # CRITICAL FIX: Expanded to 36 to fit UUIDs safely
    entity_id: Mapped[str] = mapped_column(String(36), index=True)
    
    action: Mapped[str] = mapped_column(String(100))
    actor_type: Mapped[ActorType] = mapped_column(
        SQLEnum(
            ActorType,
            name="actor_type_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        )
    )
    actor_id: Mapped[str] = mapped_column(String(36)) # ID of the system, merchant, or admin
    
    changes: Mapped[dict[str, Any]] = mapped_column(JSONB) 
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    
    # CRITICAL FIX: Traceability back to the request
    correlation_id: Mapped[Optional[str]] = mapped_column(String(36), index=True, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)