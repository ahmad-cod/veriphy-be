from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID

class SMSVerificationPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    
    merchant_id: UUID
    sms_body: str = Field(..., min_length=10, max_length=1000)
    sender_id: str = Field(..., min_length=2, max_length=50)
    
    # Security Attestation
    attestation_token: str = Field(..., min_length=20)

class SMSVerificationResponse(BaseModel):
    merchant_id: UUID
    sender_id: str
    extracted_amount: Optional[float] = None
    extracted_transaction_ref: Optional[str] = None
    extraction_confidence: float
    squad_record_found: bool
    squad_status: Optional[str] = None
    squad_amount_matched: Optional[bool] = None
    squad_record: Optional[Dict[str, Any]] = None
    message: str = Field(..., description="High-level summary of what happened during verification")
