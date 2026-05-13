from pydantic import BaseModel, Field, ConfigDict, StringConstraints
from typing import Optional, Annotated
from uuid import UUID
from datetime import datetime

from src.domain.models import KycStatus

# --- INPUT: Request Schema ---
class MerchantOnboardRequest(BaseModel):
    """
    Defines exactly what the API expects from the client.
    Handles strict input validation before it ever touches the service layer.
    """
    phone: Annotated[
        str,
        StringConstraints(pattern=r'^\+234\d{10}$')
    ] = Field(
        ..., 
        description="Enter in Nigerian phone number format (e.g., +2348012345678)",
        examples=["+2348012345678"]
    )
    bvn: Annotated[
        str,
        StringConstraints(pattern=r'^\d{11}$', strip_whitespace=True)
    ] = Field(
        ..., 
        description="Plaintext BVN. Must be exactly 11 digits.",
        examples=["12345678901"]
    )
    first_name: str = Field(..., min_length=2, max_length=50)
    last_name: str = Field(..., min_length=2, max_length=50)

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid"              # Reject unknown fields
    )


# --- OUTPUT: Response Schema ---
class MerchantResponse(BaseModel):
    """
    Defines exactly what the API returns to the client.
    Acts as a whitelist, stripping out all internal or sensitive database fields.
    """
    id: UUID
    phone: str
    kyc_status: KycStatus
    squad_account: Optional[str] = None
    squad_bank_code: Optional[str] = None
    created_at: datetime
    
    # CRITICAL: This tells Pydantic to read data from the SQLAlchemy ORM object
    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda dt: dt.isoformat()
        }
    )