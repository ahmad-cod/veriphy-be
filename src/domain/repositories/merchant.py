from typing import Optional, Sequence
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.domain.repositories.base import BaseRepository
from src.domain.models import Merchant, KycStatus

class MerchantRepository(BaseRepository[Merchant]):
    def __init__(self, session: AsyncSession):
        super().__init__(Merchant, session)

    async def get_by_phone(self, phone: str) -> Optional[Merchant]:
        """Fetches a merchant by phone, strictly enforcing soft-delete checks."""
        stmt = select(Merchant).where(
            Merchant.phone == phone,
            Merchant.is_active == True
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_bvn_hash(self, bvn_hash: str) -> Optional[Merchant]:
        """Checks for duplicate BVNs, preventing banned/deleted users from re-registering."""
        stmt = select(Merchant).where(
            Merchant.bvn_hash == bvn_hash,
            Merchant.is_active == True
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_squad_account(self, virtual_account: str) -> Optional[Merchant]:
        """Used to map incoming Squad settlement webhooks back to the correct merchant."""
        stmt = select(Merchant).where(
            Merchant.squad_account == virtual_account,
            Merchant.is_active == True
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_pending_kyc(self, limit: int = 50) -> Sequence[Merchant]:
        """Used by the background worker to sweep for merchants stuck in KYC."""
        stmt = select(Merchant).where(
            Merchant.kyc_status == KycStatus.PENDING,
            Merchant.is_active == True
        ).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()