from fastapi import APIRouter, Depends, status
import structlog

from src.api.v1.schemas.merchant import MerchantOnboardRequest, MerchantResponse
from src.api.dependencies import get_uow
from src.domain.repositories.unit_of_work import UnitOfWork
from src.domain.services.merchant_service import MerchantService

router = APIRouter(prefix="/merchants", tags=["Merchants"])
logger = structlog.get_logger()

@router.post("/", response_model=MerchantResponse, status_code=status.HTTP_201_CREATED)
async def onboard_merchant(
    payload: MerchantOnboardRequest,
    uow: UnitOfWork = Depends(get_uow),
):
    correlation_context = structlog.contextvars.get_contextvars()
    correlation_id = correlation_context.get("request_id", "unknown")

    service = MerchantService(uow)
    return await service.onboard_merchant(payload, correlation_id)
