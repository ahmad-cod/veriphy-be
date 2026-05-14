from uuid import UUID
from datetime import datetime, timezone
import hashlib

from sqlalchemy.exc import IntegrityError
from src.domain.repositories.unit_of_work import UnitOfWork
from src.domain.crypto import PIICryptoService
from src.core.exceptions import VeriphyException
from src.domain.models import JobState
from src.api.v1.schemas.verification import SMSVerificationPayload, VerificationAcceptedResponse


class VerificationService:
    def __init__(self):
        self.crypto = PIICryptoService()

    async def ingest_sms(
        self,
        payload: SMSVerificationPayload,
        merchant_id: UUID,
        correlation_id: str,
        uow: UnitOfWork
    ) -> VerificationAcceptedResponse:
        """Secure SMS ingestion with idempotency and PII protection."""

        # 1. Anti-replay hash
        hash_input = f"{merchant_id}:{payload.sender_id}:{payload.received_at_timestamp}:{payload.sms_body}"
        sms_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()

        async with uow:                                 # Proper UoW usage
            # Idempotency check
            existing = await uow.verification_jobs.get_by_sms_hash(sms_hash)
            if existing:
                return VerificationAcceptedResponse(
                    job_id=existing.id,
                    status="already_exists",
                    message="Verification already in progress",
                    queued_at=datetime.now(timezone.utc),
                    is_new=False
                )

            # 2. Encrypt SMS content (never store plaintext)
            encryption_context = {"purpose": "verification_job", "merchant_id": str(merchant_id)}
            encrypted_body = await self.crypto.encrypt_data(
                payload.sms_body,
                context=encryption_context
            )

            # 3. Create job
            job_data = {
                "merchant_id": merchant_id,
                "sms_content_encrypted": encrypted_body, 
                "sms_hash": sms_hash,
                "state": JobState.RECEIVED,
                "extracted_sender": payload.sender_id,
            }

            try:
                new_job = await uow.verification_jobs.create(job_data)

                await uow.session.flush()  # Ensure job ID is generated before commit

                # 4. Audit (implement AuditLogRepository later)
                # await uow.audit_logs.create({...})

                await uow.commit()

                return VerificationAcceptedResponse(
                    job_id=new_job.id,
                    status="accepted",
                    message="Verification job queued successfully",
                    queued_at=datetime.now(timezone.utc),
                    is_new=True
                )
            # 4. Handle Race Conditions safely
            except IntegrityError:
                await uow.rollback()
                # If we hit IntegrityError, a concurrent request beat us to it.
                # Safe to fetch the now-existing job and return it.
                existing_job = await uow.verification_jobs.get_by_sms_hash(sms_hash)
                if not existing_job:
                    raise VeriphyException("Failed to retrieve existing verification job after race condition")
                return VerificationAcceptedResponse(
                    job_id=existing_job.id,
                    message="Verification already in progress",
                    queued_at=datetime.now(timezone.utc),
                    is_new=False
                )