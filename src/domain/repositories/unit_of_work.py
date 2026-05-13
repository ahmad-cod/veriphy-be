from sqlalchemy.ext.asyncio import AsyncSession
from src.domain.repositories.merchant import MerchantRepository
from src.domain.repositories.audit import AuditLogRepository 

class UnitOfWork:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.merchants = MerchantRepository(session)
        self.audit_logs = AuditLogRepository(session)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, traceback):
        if exc_type is not None:
            await self.rollback()
        # Note: We do NOT auto-commit on success. Services must call .commit() explicitly 
        # to ensure intentional database writes.

    async def commit(self):
        await self.session.commit()

    async def rollback(self):
        await self.session.rollback()