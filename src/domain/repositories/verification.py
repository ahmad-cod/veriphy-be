from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.domain.repositories.base import BaseRepository
from src.domain.models import VerificationJob

class VerificationJobRepository(BaseRepository[VerificationJob]):
    def __init__(self, session: AsyncSession):
        super().__init__(VerificationJob, session)

    async def get_by_sms_hash(self, sms_hash: str) -> Optional[VerificationJob]:
        stmt = select(VerificationJob).where(VerificationJob.sms_hash == sms_hash)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()