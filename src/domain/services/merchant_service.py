import re
from typing import Optional
from src.domain.repositories.unit_of_work import UnitOfWork
from src.domain.crypto import PIICryptoService
from src.core.exceptions import VeriphyException
from src.domain.models import KycStatus, ActorType

# Assuming schemas are in an accessible module (e.g., api/v1/schemas.py)
from src.api.v1.schemas.merchant import MerchantOnboardRequest, MerchantResponse

class MerchantService:
    def __init__(self, uow: UnitOfWork):
        self.uow = uow
        self.crypto = PIICryptoService()

    async def onboard_merchant(self, req: MerchantOnboardRequest, correlation_id: str) -> MerchantResponse:
        """
        Transactional onboarding flow returning Pydantic schemas.
        """
        # Defensive Input Validation (Secondary to Pydantic for core business rules)
        if not re.match(r'^\d{11}$', req.bvn):
            raise VeriphyException("BVN must be exactly 11 digits", status_code=400)

        # Start explicit transaction
        async with self.uow:
            # Idempotency Check: Does phone exist?
            existing_merchant = await self.uow.merchants.get_by_phone(req.phone)
            if existing_merchant:
                if existing_merchant.kyc_status == KycStatus.PENDING:
                    return MerchantResponse.model_validate(existing_merchant)
                raise VeriphyException("Phone number already registered and processed.", status_code=409)

            # Security: Hash BVN & Check uniqueness to prevent race conditions
            bvn_hash = self.crypto.hash_pii(req.bvn)
            existing_bvn = await self.uow.merchants.get_by_bvn_hash(bvn_hash)
            if existing_bvn:
                raise VeriphyException("BVN is already linked to an active account.", status_code=409)

            # Security: True Envelope Encryption
            encryption_context = {"purpose": "kyc_bvn", "phone": req.phone}
            bvn_encrypted = await self.crypto.encrypt_data(req.bvn, context=encryption_context)

            # 1. Create Merchant
            merchant_data = {
                "phone": req.phone,
                "bvn_encrypted": bvn_encrypted,
                "bvn_hash": bvn_hash,
                "kyc_status": KycStatus.PENDING
            }
            new_merchant = await self.uow.merchants.create(merchant_data)

            # 2. Create Audit Log in the SAME transaction
            await self.uow.audit_logs.create({
                "entity_type": "Merchant",
                "entity_id": str(new_merchant.id),
                "action": "MERCHANT_ONBOARDED_PENDING",
                "actor_type": ActorType.SYSTEM,
                "actor_id": "system",
                "correlation_id": correlation_id,
                "changes": {"phone": req.phone, "kyc_status": "pending"}
            })

            # Commit the Unit of Work (Atomic success)
            await self.uow.commit()
            
            # (Phase 4 Hook: Trigger Celery Task here to call Squad API)

            # Return Pydantic object (safe for API layer)
            return MerchantResponse.model_validate(new_merchant)