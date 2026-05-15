from cryptography.fernet import Fernet
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr, model_validator, field_validator, Field
from typing import List, Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "Veri-phy API"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = Field(...)
        
    # Require injection, no hardcoded credentials
    DATABASE_URL: str = Field(...)
    REDIS_URL: str = Field(...)

    JWT_SECRET_KEY: SecretStr = Field(...)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    
    CORS_ORIGINS: List[str] = [] # Stricter typing for CORS configuration
    
    AWS_REGION: Optional[str] = None
    AWS_KMS_KEY_ID: Optional[str] = None
    BVN_HASH_PEPPER: SecretStr = Field(...)
    
    SQUAD_API_URL: str = "https://sandbox-api-d.squadco.com"
    SQUAD_SECRET_KEY: SecretStr = Field(...)

    SMS_HMAC_SECRET: SecretStr = Field(...)
    LOCAL_DEK: Optional[SecretStr] = None

    # Google Play Integrity API
    GOOGLE_PLAY_INTEGRITY_API_KEY: Optional[SecretStr] = None
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8", 
        extra="ignore"
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def validate_cors_origins(cls, v):
        if isinstance(v, str):
            import json
            return json.loads(v)
        return v
    
    @model_validator(mode="after")
    def validate_environment_settings(self) -> "Settings":
        if self.ENVIRONMENT == "production":
            if not self.AWS_KMS_KEY_ID:
                raise ValueError("AWS_KMS_KEY_ID is strictly required in production.")
            if not self.GOOGLE_PLAY_INTEGRITY_API_KEY:
                raise ValueError("GOOGLE_PLAY_INTEGRITY_API_KEY is strictly required in production.")
            if not self.CORS_ORIGINS:
                self.CORS_ORIGINS = ["https://admin.veriphy.ng"]
        elif self.ENVIRONMENT == "staging":
            if not self.CORS_ORIGINS:
                self.CORS_ORIGINS = ["https://staging-admin.veriphy.ng"]
        elif self.ENVIRONMENT == "local":
            if not self.CORS_ORIGINS:
                self.CORS_ORIGINS = ["*"]
            if not self.LOCAL_DEK:
                raise ValueError("LOCAL_DEK is required in local environment to support deterministic PII encryption.")
            try:
                Fernet(self.LOCAL_DEK.get_secret_value().encode())
            except Exception as exc:
                raise ValueError(
                    "LOCAL_DEK must be a 32-byte url-safe base64-encoded Fernet key. "
                    "Generate one with Fernet.generate_key()."
                ) from exc
        return self

settings = Settings()