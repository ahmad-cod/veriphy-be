import pytest
from unittest.mock import AsyncMock
from uuid import UUID
from datetime import datetime, timezone

from src.domain.services.verification_service import VerificationService
from src.api.v1.schemas.verification import SMSVerificationPayload


@pytest.mark.asyncio
async def test_verify_sms_returns_squad_record_when_transaction_ref_exists():
    payload = SMSVerificationPayload(
        merchant_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
        sms_body="Your payment of NGN 1,200.00 was successful. Transaction ref: SQABC1234.",
        sender_id="Veriphy",
        received_at_timestamp=int(datetime.now(timezone.utc).timestamp()),
        attestation_token="a" * 32,
    )
    service = VerificationService()
    service.squad_client.verify_transaction_by_ref = AsyncMock(return_value={
        "transaction_reference": "SQABC1234",
        "transaction_amount": 1200.0,
        "status": "success",
        "created_at": "2026-05-15T11:00:00Z",
    })

    response = await service.verify_sms(payload, "corr-id")

    assert response.squad_record_found is True
    assert response.extracted_transaction_ref == "SQABC1234"
    assert response.squad_amount_matched is True
    assert response.squad_status == "success"
    assert response.message == "Squad record found and verified."


@pytest.mark.asyncio
async def test_verify_sms_skips_squad_lookup_without_transaction_ref():
    payload = SMSVerificationPayload(
        merchant_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
        sms_body="Your account was credited with NGN 1500.00.",
        sender_id="Veriphy",
        received_at_timestamp=int(datetime.now(timezone.utc).timestamp()),
        attestation_token="a" * 32,
    )
    service = VerificationService()
    service.squad_client.verify_transaction_by_ref = AsyncMock()

    response = await service.verify_sms(payload, "corr-id")

    assert response.squad_record_found is False
    assert response.extracted_transaction_ref is None
    assert response.squad_amount_matched is None
    assert response.message == "No transaction reference extracted; Squad lookup skipped."
    service.squad_client.verify_transaction_by_ref.assert_not_awaited()


@pytest.mark.asyncio
async def test_verify_sms_handles_squad_record_found_but_amount_mismatch():
    payload = SMSVerificationPayload(
        merchant_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
        sms_body="Your payment of NGN 1,200.00 was successful. Transaction ref: SQXYZ5678.",
        sender_id="Veriphy",
        received_at_timestamp=int(datetime.now(timezone.utc).timestamp()),
        attestation_token="a" * 32,
    )
    service = VerificationService()
    service.squad_client.verify_transaction_by_ref = AsyncMock(return_value={
        "transaction_reference": "SQXYZ5678",
        "transaction_amount": 1300.0,
        "status": "success",
        "created_at": "2026-05-15T11:00:00Z",
    })

    response = await service.verify_sms(payload, "corr-id")

    assert response.squad_record_found is True
    assert response.squad_amount_matched is False
    assert response.message == "Squad record found but amount did not match."
