import asyncio
from celery import Celery
from celery.signals import worker_process_init
from celery.exceptions import SoftTimeLimitExceeded
from uuid import UUID
import structlog

from src.core.config import settings
from src.infrastructure.database import AsyncSessionLocal
from src.domain.repositories.unit_of_work import UnitOfWork
from src.domain.services.orchestrator import VerificationOrchestrator
from src.domain.ai.nlp import NLPExtractor

celery_app = Celery("veriphy_worker", broker=settings.REDIS_URL, backend=settings.REDIS_URL)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_soft_time_limit=300,   # 5 minutes soft limit
    task_time_limit=360,        # 6 minutes hard kill
)

@worker_process_init.connect
def init_worker(**kwargs):
    """Fires when a Celery worker process boots up. Warms up the heavy AI models."""
    logger = structlog.get_logger()
    logger.info("Initializing worker process dependencies...")
    NLPExtractor.load_models()

@celery_app.task(name="tasks.process_verification", bind=True, max_retries=5, default_retry_delay=30)
def process_verification_job(self, job_id_str: str, correlation_id: str):
    
    structlog.contextvars.bind_contextvars(
        request_id=correlation_id, 
        celery_task_id=self.request.id
    )
    logger = structlog.get_logger()
    logger.info("Starting verification job", job_id=job_id_str)

    async def run():
        async with AsyncSessionLocal() as session:
            uow = UnitOfWork(session)
            orchestrator = VerificationOrchestrator(uow)
            return await orchestrator.process_job(UUID(job_id_str), correlation_id)

    try:
        # Run the async orchestration synchronously inside the Celery worker
        return asyncio.run(run())
        
    except SoftTimeLimitExceeded:
        logger.warning("Task hit soft time limit, re-queueing", job_id=job_id_str)
        raise self.retry(exc=SoftTimeLimitExceeded(), countdown=60)
        
    except ValueError as e:
        # Non-retryable error (e.g., Job not found)
        logger.error("Job validation failed. Not retrying.", job_id=job_id_str, error=str(e))
        raise
        
    except Exception as exc:
        logger.error("Job failed, preparing to retry", job_id=job_id_str, exc_info=True)
        # Exponential backoff for network/transient errors
        raise self.retry(exc=exc, countdown=2 ** min(self.request.retries, 5))
    