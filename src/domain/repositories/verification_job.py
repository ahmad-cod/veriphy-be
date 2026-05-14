from typing import Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models import VerificationJob
from src.domain.repositories.base import BaseRepository   # Assuming you have this

class VerificationJobRepository(BaseRepository[VerificationJob]):
    def __init__(self, session: AsyncSession):
        super().__init__(VerificationJob, session)

    async def get_by_sms_hash(self, sms_hash: str) -> Optional[VerificationJob]:
        """Idempotency check for SMS ingestion."""
        stmt = select(VerificationJob).where(VerificationJob.sms_hash == sms_hash)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, obj_in: dict) -> VerificationJob:
        """Override to ensure we use proper model creation."""
        db_obj = VerificationJob(**obj_in)
        self.session.add(db_obj)
        await self.session.flush()   # Get ID without committing
        return db_obj