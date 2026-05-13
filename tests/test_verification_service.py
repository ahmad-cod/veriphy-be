import pytest
from unittest.mock import AsyncMock, Mock
from uuid import UUID
from datetime import datetime, timezone

from src.domain.services.verification_service import VerificationService
from src.api.v1.schemas.verification import SMSVerificationPayload


@pytest.mark.asyncio
async def test_ingest_sms_returns_existing_job_on_duplicate():
    payload = SMSVerificationPayload(
        sms_body="Test SMS body content",
        sender_id="Veriphy",
        received_at_timestamp=int(datetime.now(timezone.utc).timestamp()),
        attestation_token="a" * 32,
    )
    existing_job = Mock(id=UUID("123e4567-e89b-12d3-a456-426614174000"))

    uow = AsyncMock()
    uow.__aenter__.return_value = uow
    uow.verification_jobs.get_by_sms_hash.return_value = existing_job

    service = VerificationService()
    response = await service.ingest_sms(payload, UUID("123e4567-e89b-12d3-a456-426614174000"), "corr-id", uow)

    assert response.is_new is False
    assert response.job_id == existing_job.id
    assert response.status == "already_exists"


@pytest.mark.asyncio
async def test_ingest_sms_creates_new_job_when_not_duplicate():
    payload = SMSVerificationPayload(
        sms_body="Another SMS body example",
        sender_id="Veriphy",
        received_at_timestamp=int(datetime.now(timezone.utc).timestamp()),
        attestation_token="a" * 32,
    )
    new_job = Mock(id=UUID("123e4567-e89b-12d3-a456-426614174001"))

    uow = AsyncMock()
    uow.__aenter__.return_value = uow
    uow.verification_jobs.get_by_sms_hash.return_value = None
    uow.verification_jobs.create.return_value = new_job
    uow.session.flush = AsyncMock()
    uow.commit = AsyncMock()

    service = VerificationService()
    response = await service.ingest_sms(payload, UUID("123e4567-e89b-12d3-a456-426614174000"), "corr-id", uow)

    assert response.is_new is True
    assert response.job_id == new_job.id
    assert response.status == "accepted"
    uow.verification_jobs.create.assert_awaited_once()
    uow.commit.assert_awaited_once()
