from typing import Sequence
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from src.domain.repositories.base import BaseRepository
from src.domain.models import AuditLog

class AuditLogRepository(BaseRepository[AuditLog]):
    def __init__(self, session: AsyncSession):
        super().__init__(AuditLog, session)

    async def update(self, *args, **kwargs):
        """Override to prevent mutation of the audit trail."""
        raise NotImplementedError("Audit logs are immutable and cannot be updated.")

    async def soft_delete(self, *args, **kwargs):
        """Override to prevent deletion of the audit trail."""
        raise NotImplementedError("Audit logs are immutable and cannot be deleted.")

    async def hard_delete(self, *args, **kwargs):
        """Override to prevent deletion of the audit trail."""
        raise NotImplementedError("Audit logs are immutable and cannot be deleted.")

    async def list_by_entity(self, entity_type: str, entity_id: str, limit: int = 50) -> Sequence[AuditLog]:
        """
        Retrieves the chronological history of a specific resource (e.g., a VerificationJob's state changes).
        """
        stmt = select(AuditLog).where(
            AuditLog.entity_type == entity_type,
            AuditLog.entity_id == entity_id
        ).order_by(desc(AuditLog.created_at)).limit(limit)
        
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_by_correlation_id(self, correlation_id: str) -> Sequence[AuditLog]:
        """
        Retrieves all system events tied to a single API request, spanning across merchants, jobs, and ledger writes.
        """
        stmt = select(AuditLog).where(
            AuditLog.correlation_id == correlation_id
        ).order_by(AuditLog.created_at)
        
        result = await self.session.execute(stmt)
        return result.scalars().all()