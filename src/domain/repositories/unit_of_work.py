from sqlalchemy.ext.asyncio import AsyncSession
from src.domain.repositories.merchant import MerchantRepository
from src.domain.repositories.verification_job import VerificationJobRepository
from src.domain.repositories.audit import AuditLogRepository

class UnitOfWork:
    """Async Unit of Work pattern - manages transaction boundary."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.merchants = MerchantRepository(session)
        self.verification_jobs = VerificationJobRepository(session)
        self.audit_logs = AuditLogRepository(session)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            await self.rollback()
        else:
            await self.commit()
        # Do not close session here if managed by FastAPI dependency

    async def commit(self):
        await self.session.commit()

    async def rollback(self):
        await self.session.rollback()