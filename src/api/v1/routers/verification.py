from fastapi import APIRouter, status
import structlog

from src.api.v1.schemas.verification import SMSVerificationPayload, SMSVerificationResponse
from src.api.dependencies import verify_play_integrity
from src.domain.services.verification_service import VerificationService

router = APIRouter(prefix="/verify", tags=["Verification"])
logger = structlog.get_logger()

@router.post(
    "/sms",
    response_model=SMSVerificationResponse,
)
async def submit_sms_verification(
    payload: SMSVerificationPayload,
):
    # 1. Google Play Integrity Check
    await verify_play_integrity(payload.attestation_token)

    # 2. Extract correlation context
    context = structlog.contextvars.get_contextvars()
    correlation_id = context.get("request_id", "unknown")

    # 3. Perform SMS extraction and Squad lookup directly
    service = VerificationService()
    response = await service.verify_sms(payload, correlation_id)
    return response