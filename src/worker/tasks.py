from celery import Celery
import asyncio
from uuid import UUID
from sqlalchemy import select

import structlog
from src.core.config import settings
from src.domain.crypto import PIICryptoService
from src.domain.models import VerificationJob, JobState
from src.infrastructure.database import AsyncSessionLocal

logger = structlog.get_logger()
celery_app = Celery("veriphy_worker", broker=settings.REDIS_URL)
celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.accept_content = ["json"]
celery_app.conf.task_ignore_result = True

@celery_app.task(name="tasks.process_verification_job", bind=True, max_retries=3)
def process_verification_job(self, job_id: str, correlation_id: str):
    """Background worker for verification job orchestration."""

    async def run_pipeline() -> None:
        async with AsyncSessionLocal() as session:
            stmt = select(VerificationJob).where(VerificationJob.id == UUID(job_id))
            result = await session.execute(stmt)
            job = result.scalar_one_or_none()
            if job is None:
                raise RuntimeError(f"Verification job not found: {job_id}")

            crypto = PIICryptoService()
            decrypted_sms = await crypto.decrypt_data(
                job.sms_content_encrypted,
                {"purpose": "verification_job", "merchant_id": str(job.merchant_id)},
            )
            logger.info("Verification job decrypted", job_id=job_id)

            job.state = JobState.PROCESSING_AI
            session.add(job)
            await session.commit()

            # TODO: Implement NLP extraction, Squad orchestration, and final state transitions.
            logger.info("Verification worker placeholder completed", job_id=job_id, correlation_id=correlation_id)

    try:
        asyncio.run(run_pipeline())
    except Exception as exc:
        logger.error("Verification worker failed", job_id=job_id, error=str(exc), exc_info=True)
        raise self.retry(exc=exc, countdown=10)
