from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID
from src.domain.repositories.unit_of_work import UnitOfWork
from src.domain.crypto import PIICryptoService
from src.domain.models import JobState, ActorType
from src.domain.ai.nlp import NLPExtractor
from src.infrastructure.squad import SquadAPIClient
import structlog

logger = structlog.get_logger()

class VerificationOrchestrator:
    def __init__(self, uow: UnitOfWork):
        self.uow = uow
        self.crypto = PIICryptoService()
        self.squad_client = SquadAPIClient()

    async def process_job(self, job_id: UUID, correlation_id: str) -> str:
        # --- SAGA PHASE 1: Initialization & AI State ---
        async with self.uow:
            job = await self.uow.verification_jobs.get_by_id(job_id)
            if not job:
                logger.warning("Verification job not found", job_id=str(job_id), correlation_id=correlation_id)
                return "NOT_FOUND"

            if job.state in [JobState.RESOLVED_VERIFIED, JobState.RESOLVED_FAKE, JobState.RESOLVED_TIMEOUT]:
                logger.info("Verification job already in terminal state", job_id=str(job_id), state=job.state.value)
                return job.state.value

            merchant = await self.uow.merchants.get_by_id(job.merchant_id)
            if not merchant:
                logger.error("Merchant not found for verification job", job_id=str(job_id), merchant_id=str(job.merchant_id), correlation_id=correlation_id)
                raise RuntimeError("Merchant not found for verification job")

            if not merchant.squad_account:
                job.state = JobState.AWAITING_SQUAD
                job.resolution_reason = "MISSING_SQUAD_ACCOUNT"
                await self._log_audit(job.id, "AWAITING_SQUAD_MISSING_ACCOUNT", correlation_id)
                return job.state.value

            job.state = JobState.PROCESSING_AI
            await self._log_audit(job.id, "STARTED_AI_PROCESSING", correlation_id)

            # Fetch decrypted SMS payload for extraction outside the DB lock
            encryption_context = {"purpose": "verification_job", "merchant_id": str(merchant.id)}
            decrypted_sms = await self.crypto.decrypt_data(job.sms_content_encrypted, context=encryption_context)
            squad_account = merchant.squad_account

        # --- SAGA PHASE 2: Heavy Lifting (NO DB LOCKS) ---
        extracted = NLPExtractor.extract_financial_entities(decrypted_sms)
        amount = extracted.get("amount")

        if not amount or amount <= 0:
            async with self.uow:
                job = await self.uow.verification_jobs.get_by_id(job_id)
                if job is None:
                  logger.error("Job vanished during processing", job_id=str(job_id))
                  return "ERROR_STALE_JOB"
                
                job.state = JobState.RESOLVED_FAKE
                job.resolution_reason = "NLP_NO_AMOUNT_FOUND"
                job.resolved_at = datetime.now(timezone.utc)
                await self._log_audit(job.id, "RESOLVED_FAKE", correlation_id)
                return job.state.value

        # --- SAGA PHASE 3: Ledger State & External Request ---
        async with self.uow:
            job = await self.uow.verification_jobs.get_by_id(job_id)
            if job:
              
              # Convert amount from float to string, then to Decimal for exact precision
              job.extracted_amount = Decimal(str(amount))
              job.state = JobState.PROCESSING_LEDGER
              await self.uow.commit()  # Commit before external call to minimize lock duration  
              await self._log_audit(job.id, "STARTED_LEDGER_CHECK", correlation_id)

        squad_match = await self.squad_client.verify_transaction(
            amount=int(amount) * 100,  # Squad expects amount in smallest currency unit (e.g., kobo)
            virtual_account=squad_account
        )

        # --- SAGA PHASE 4: Final Resolution ---
        async with self.uow:
            job = await self.uow.verification_jobs.get_by_id(job_id)
            if job is None:
              logger.error("Job vanished during processing", job_id=str(job_id))
              return "ERROR_STALE_JOB"

            if squad_match:
                job.state = JobState.RESOLVED_VERIFIED
                job.squad_txn_ref = squad_match.get("transaction_reference")
                job.resolution_reason = "SQUAD_API_MATCH"
                job.resolved_at = datetime.now(timezone.utc)
            else:
                job.state = JobState.AWAITING_SQUAD
                job.resolution_reason = "PENDING_SETTLEMENT"

            await self._log_audit(job.id, f"STATE_CHANGED_TO_{job.state.name}", correlation_id)
            return job.state.value

    async def _log_audit(self, job_id: UUID, action: str, correlation_id: str):
        await self.uow.audit_logs.create({
            "entity_type": "VerificationJob",
            "entity_id": str(job_id),
            "action": action,
            "actor_type": ActorType.SYSTEM,
            "actor_id": "celery_worker",
            "correlation_id": correlation_id,
            "changes": {}
        })