from decimal import Decimal
from typing import Dict, Optional
from src.domain.ai.nlp import NLPExtractor
from src.infrastructure.squad import SquadAPIClient
from src.api.v1.schemas.verification import SMSVerificationPayload, SMSVerificationResponse


class VerificationService:
    def __init__(self):
        self.squad_client = SquadAPIClient()

    async def verify_sms(
        self,
        payload: SMSVerificationPayload,
        correlation_id: str,
    ) -> SMSVerificationResponse:
        """Extract financial entities from SMS and verify against Squad without persistence."""
        extracted = NLPExtractor.extract_financial_entities(payload.sms_body)
        amount = Decimal(str(extracted.get("amount", None))) * 100 if extracted.get("amount") is not None else None  # Convert to kobo / cents if amount is present
        transaction_ref = extracted.get("transaction_ref")
        confidence_score = extracted.get("confidence_score", 0.0)

        squad_record = None
        squad_record_found = False
        squad_status = None
        squad_amount_matched: Optional[bool] = None

        if transaction_ref:
            squad_record = await self.squad_client.verify_transaction_by_ref(transaction_ref)
            squad_record_found = squad_record is not None
            if squad_record_found:
                squad_status = squad_record.get("status") or squad_record.get("transaction_status")
                if amount is not None:
                    try:
                        squad_amount = float(squad_record.get("transaction_amount", squad_record.get("amount", 0)))
                        squad_amount_matched = abs(squad_amount - float(amount)) < 0.01
                    except (TypeError, ValueError):
                        squad_amount_matched = False

        if transaction_ref is None:
            message = "No transaction reference extracted; Squad lookup skipped."
        elif squad_record_found:
            message = "Squad record found and verified." if squad_amount_matched else "Squad record found but amount did not match."
        else:
            message = "Transaction reference extracted; no Squad record was found."

        return SMSVerificationResponse(
            merchant_id=payload.merchant_id,
            sender_id=payload.sender_id,
            extracted_amount=amount,
            extracted_transaction_ref=transaction_ref,
            extraction_confidence=confidence_score,
            squad_record_found=squad_record_found,
            squad_status=squad_status,
            squad_amount_matched=squad_amount_matched,
            squad_record=squad_record,
            message=message,
        )
