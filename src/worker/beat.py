import asyncio
from datetime import datetime, timezone, timedelta
from celery import Celery
import structlog
from sqlalchemy import select

from src.core.config import settings
from src.infrastructure.database import AsyncSessionLocal
from src.infrastructure.redis import redis_client
from src.domain.repositories.unit_of_work import UnitOfWork
from src.domain.models import JobState, VerificationJob
from src.worker.tasks import process_verification_job

celery_beat = Celery("veriphy_beat", broker=settings.REDIS_URL)
logger = structlog.get_logger()

celery_beat.conf.beat_schedule = {
    "sweep-pending-ledger-jobs": {
        "task": "beat.sweep_awaiting_squad",
        "schedule": 60.0,
    },
}

@celery_beat.task(name="beat.sweep_awaiting_squad", bind=True)
def sweep_awaiting_squad(self):
    lock_key = "lock:beat:sweep_awaiting"

    async def run_sweep():
        # 1. Distributed Lock to prevent overlapping cron jobs
        if redis_client:
          if not await redis_client.set(lock_key, "1", nx=True, ex=50):
              logger.info("Sweep already running, skipping")
              return

          try:
              async with AsyncSessionLocal() as session:
                  uow = UnitOfWork(session)
                  async with uow:
                      # 2. Row-level Lock (SKIP LOCKED) to prevent DB contention
                      stmt = select(VerificationJob).where(
                          VerificationJob.state == JobState.AWAITING_SQUAD
                      ).with_for_update(skip_locked=True)
                      
                      result = await uow.session.execute(stmt)
                      stuck_jobs = result.scalars().all()
                      
                      now = datetime.now(timezone.utc)
                      timeout_threshold = now - timedelta(minutes=15)
                      
                      for job in stuck_jobs:
                          if job.created_at < timeout_threshold:
                              job.state = JobState.RESOLVED_TIMEOUT
                              job.resolution_reason = "15_MIN_SLA_EXCEEDED"
                              logger.warning("Job timed out", job_id=str(job.id))
                          else:
                              logger.info("Re-queueing pending job", job_id=str(job.id))
                              process_verification_job.apply_async( # type: ignore[attr-defined]
                                  args=[str(job.id), f"beat-sweep-{now.timestamp()}"],
                                  queue="ai_inference"
                              )
                      await uow.commit()
          finally:
              # 3. Release Distributed Lock
              await redis_client.delete(lock_key)

    asyncio.run(run_sweep())