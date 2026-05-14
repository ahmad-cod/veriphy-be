import hashlib
import hmac
from typing import AsyncGenerator
from uuid import UUID

from fastapi import Header, HTTPException, Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError

from src.core.config import settings
from src.core.exceptions import AuthenticationError
from src.core.security import decode_access_token
import structlog
from src.infrastructure.database import get_db_session
from src.domain.repositories.unit_of_work import UnitOfWork
from src.infrastructure.redis import get_redis

logger = structlog.get_logger()

async def get_uow(session: AsyncSession = Depends(get_db_session)) -> UnitOfWork:
    """Injects the async session into the Unit of Work."""
    return UnitOfWork(session)

async def verify_merchant_jwt(authorization: str = Header(...)) -> UUID:
    """Decodes and verifies the Authorization bearer token."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Invalid authorization header format")

    try:
        return decode_access_token(token)
    except AuthenticationError as exc:
        raise HTTPException(status_code=401, detail=exc.message) from exc
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid JWT token")

async def verify_play_integrity(token: str):
    """
    Verify Google Play Integrity token to ensure app authenticity and device integrity.

    This checks that:
    - The app is untampered and downloaded from Google Play Store
    - The device meets integrity requirements (not rooted, not compromised)
    - The request is legitimate and not from a malicious source
    """
    if not token or len(token) < 20:
        raise HTTPException(status_code=403, detail="Invalid attestation token")

    # Skip verification in local development for easier testing
    if settings.ENVIRONMENT == "local":
        logger.info("Skipping Google Play Integrity check in local environment")
        return

    # Import here to avoid circular imports
    from src.infrastructure.google_play import GooglePlayIntegrityClient

    try:
        client = GooglePlayIntegrityClient()
        result = await client.verify_app_integrity(token)

        if not result.get("verified", False):
            raise HTTPException(status_code=403, detail="App integrity verification failed")

        logger.info("Google Play Integrity verification passed")

    except Exception as e:
        logger.error("Google Play Integrity verification failed", error=str(e))
        raise HTTPException(status_code=403, detail="App integrity verification failed")

async def verify_sms_ingress(
    request: Request,
    x_payload_signature: str = Header(...),
    merchant_id: UUID = Depends(verify_merchant_jwt)
) -> UUID:
    """Consolidated security gate for the hot path."""
    """Prevents Man-in-the-Middle tampering of the SMS payload."""
    body = await request.body()
    
    # Use dedicated SMS HMAC secret, NOT the JWT secret
    secret = settings.SMS_HMAC_SECRET.get_secret_value().encode()
    expected_hmac = hmac.new(secret, body, hashlib.sha256).hexdigest()
    
    if not hmac.compare_digest(expected_hmac, x_payload_signature):
        logger.warning("HMAC signature mismatch", merchant_id=str(merchant_id))
        raise HTTPException(status_code=403, detail="Invalid payload signature")
    
    return merchant_id

async def rate_limiter(
    merchant_id: UUID = Depends(verify_merchant_jwt),
    redis: Redis = Depends(get_redis),
):
    """Redis-backed sliding window rate limit: max 10 requests per minute."""
    key = f"rate_limit:sms:{merchant_id}"
    requests = await redis.incr(key)
    if requests == 1:
        await redis.expire(key, 60)
    if requests > 10:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Too many SMS verifications.")