from fastapi import APIRouter, Depends, status
from uuid import UUID
import structlog

from src.api.v1.schemas.verification import SMSVerificationPayload, VerificationAcceptedResponse
from src.api.dependencies import get_uow, verify_sms_ingress, verify_play_integrity, rate_limiter
from src.domain.services.verification_service import VerificationService
from src.domain.repositories.unit_of_work import UnitOfWork
from src.worker.tasks import process_verification_job

router = APIRouter(prefix="/verify", tags=["Verification"])
logger = structlog.get_logger()

@router.post(
    "/sms", 
    status_code=status.HTTP_202_ACCEPTED,
    response_model=VerificationAcceptedResponse,
    dependencies=[Depends(rate_limiter)] 
)
async def submit_sms_verification(
    payload: SMSVerificationPayload,
    merchant_id: UUID = Depends(verify_sms_ingress),
    uow: UnitOfWork = Depends(get_uow),
):
    # 1. Google Play Integrity Check
    await verify_play_integrity(payload.attestation_token)

    # 2. Extract correlation context
    context = structlog.contextvars.get_contextvars()
    correlation_id = context.get("request_id", "unknown")

    # 3. Securely persist via service layer
    service = VerificationService()
    response = await service.ingest_sms(payload, merchant_id, correlation_id, uow)

    # 4. Dispatch to Celery Queue (async offload)
    process_verification_job.apply_async(  # type: ignore[attr-defined]
        args=[str(response.job_id), correlation_id],
        queue="ai_inference"
    )
    
    return response