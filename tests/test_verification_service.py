import pytest
from unittest.mock import AsyncMock, Mock
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError

from src.domain.services.verification_service import VerificationService
from src.api.v1.schemas.verification import SMSVerificationPayload


@pytest.mark.asyncio
async def test_ingest_sms_returns_existing_job_on_duplicate():
    payload = SMSVerificationPayload(
        merchant_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
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
async def test_ingest_sms_returns_existing_job_after_integrity_error_race():
    payload = SMSVerificationPayload(
        merchant_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
        sms_body="Race condition example",
        sender_id="Veriphy",
        received_at_timestamp=int(datetime.now(timezone.utc).timestamp()),
        attestation_token="a" * 32,
    )
    existing_job = Mock(id=UUID("123e4567-e89b-12d3-a456-426614174000"))

    class FakeUoW:
        def __init__(self):
            self.verification_jobs = Mock()
            self.session = Mock()
            self.session.flush = AsyncMock()
            self.commit = AsyncMock()
            self.rollback = AsyncMock()
            self.verification_jobs.get_by_sms_hash = AsyncMock(side_effect=[None, None, existing_job])
            self.verification_jobs.create = AsyncMock(side_effect=IntegrityError("stmt", {}, None))

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return False

    uow = FakeUoW()

    service = VerificationService()
    response = await service.ingest_sms(payload, UUID("123e4567-e89b-12d3-a456-426614174000"), "corr-id", uow)

    assert response.is_new is False
    assert response.job_id == existing_job.id
    assert response.status == "already_exists"
    assert uow.rollback.await_count == 1


@pytest.mark.asyncio
async def test_ingest_sms_allows_default_received_at_timestamp():
    payload = SMSVerificationPayload(
        merchant_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
        sms_body="Default timestamp test content",
        sender_id="Veriphy",
        attestation_token="a" * 32,
    )
    service = VerificationService()
    assert isinstance(payload.received_at_timestamp, int)
    assert payload.received_at_timestamp > 0


@pytest.mark.asyncio
async def test_ingest_sms_creates_new_job_when_not_duplicate():
    payload = SMSVerificationPayload(
        merchant_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
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
