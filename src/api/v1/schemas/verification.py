import time
from pydantic import BaseModel, Field, ConfigDict, field_validator
from uuid import UUID
from datetime import datetime

class SMSVerificationPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    
    sms_body: str = Field(..., min_length=10, max_length=1000)
    sender_id: str = Field(..., min_length=2, max_length=50)
    received_at_timestamp: int = Field(...)
    
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

class VerificationAcceptedResponse(BaseModel):
    job_id: UUID
    status: str = "accepted"
    message: str = "Verification job queued successfully"
    queued_at: datetime
    is_new: bool = Field(..., description="True if newly created, False if idempotent retry")