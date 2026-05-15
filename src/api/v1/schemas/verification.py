import time
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, field_validator
from uuid import UUID
from datetime import datetime

class SMSVerificationPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    
    merchant_id: UUID
    sms_body: str = Field(..., min_length=10, max_length=1000)
    sender_id: str = Field(..., min_length=2, max_length=50)
    received_at_timestamp: int = Field(default_factory=lambda: int(time.time()))
    
    # Security Attestation
    attestation_token: str = Field(..., min_length=20)
    
    @field_validator('received_at_timestamp')
    @classmethod
    def validate_timestamp(cls, v: int) -> int:
        now = int(time.time())
        if now - v > 300: # 5 minute hard cutoff for replay attacks
            raise ValueError("SMS timestamp is too old. Possible replay attack.")
        if v - now > 60: # 1 minute future tolerance for clock drift
            raise ValueError("SMS timestamp is in the future.")
        return v

class SMSVerificationResponse(BaseModel):
    merchant_id: UUID
    sender_id: str
    received_at_timestamp: int
    extracted_amount: Optional[float] = None
    extracted_transaction_ref: Optional[str] = None
    extraction_confidence: float
    squad_record_found: bool
    squad_status: Optional[str] = None
    squad_amount_matched: Optional[bool] = None
    squad_record: Optional[Dict[str, Any]] = None
    message: str = Field(..., description="High-level summary of what happened during verification")