from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from jose import JWTError, jwt

from src.core.config import settings
from src.core.exceptions import AuthenticationError

ACCESS_TOKEN_SUBJECT_KEY = "sub"


def create_access_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    expiry = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    payload = {
        ACCESS_TOKEN_SUBJECT_KEY: subject,
        "exp": expiry,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY.get_secret_value(), algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> UUID:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY.get_secret_value(),
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError as exc:
        raise AuthenticationError("Invalid JWT token") from exc

    subject = payload.get(ACCESS_TOKEN_SUBJECT_KEY)
    if subject is None:
        raise AuthenticationError("Invalid JWT token payload")

    try:
        return UUID(subject)
    except ValueError as exc:
        raise AuthenticationError("Invalid token subject") from exc
