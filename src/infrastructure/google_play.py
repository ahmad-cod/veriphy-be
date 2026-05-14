import httpx
import asyncio
from typing import Optional, Dict, Any
import structlog
from src.core.config import settings
from src.core.exceptions import VeriphyException

logger = structlog.get_logger()

class GooglePlayIntegrityClient:
    """Google Play Integrity API client for app attestation verification."""

    _instance = None
    _client: Optional[httpx.AsyncClient] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GooglePlayIntegrityClient, cls).__new__(cls)
        return cls._instance

    def get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url="https://playintegrity.googleapis.com",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {settings.GOOGLE_PLAY_INTEGRITY_API_KEY}"
                },
                timeout=httpx.Timeout(10.0, connect=2.0),
                limits=httpx.Limits(max_keepalive_connections=20, max_connections=50)
            )
        return self._client

    async def verify_app_integrity(self, integrity_token: str, package_name: str = "com.veriphy.mobile") -> Dict[str, Any]:
        """
        Verify Google Play Integrity token.

        Args:
            integrity_token: The integrity token from the client app
            package_name: The Android package name

        Returns:
            Dict containing verification results with device integrity, app integrity, and account details

        Raises:
            VeriphyException: If verification fails or API errors occur
        """
        client = self.get_client()
        url = f"/v1/{package_name}:decodeIntegrityToken"

        payload = {"integrity_token": integrity_token}

        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

            # Extract token payload
            token_payload = data.get("tokenPayloadExternal", {})

            # Check device integrity
            device_integrity = token_payload.get("deviceIntegrity", {})
            app_integrity = token_payload.get("appIntegrity", {})
            account_details = token_payload.get("accountDetails", {})

            # Validate integrity signals
            device_recognition_verdict = device_integrity.get("deviceRecognitionVerdict", [])

            # Require MEETS_STRONG_INTEGRITY for production
            integrity_level = "MEETS_STRONG_INTEGRITY" if settings.ENVIRONMENT == "production" else "MEETS_BASIC_INTEGRITY"

            if integrity_level not in device_recognition_verdict:
                logger.warning(
                    "Device integrity check failed",
                    required_level=integrity_level,
                    actual_verdicts=device_recognition_verdict
                )
                raise VeriphyException(
                    f"Device integrity check failed. Required: {integrity_level}",
                    status_code=403
                )

            # Check app integrity
            app_recognition_verdict = app_integrity.get("appRecognitionVerdict", "")
            if app_recognition_verdict != "PLAY_RECOGNIZED":
                logger.warning(
                    "App integrity check failed",
                    app_verdict=app_recognition_verdict
                )
                raise VeriphyException(
                    "App integrity check failed. App not recognized by Google Play",
                    status_code=403
                )

            logger.info(
                "Google Play Integrity verification successful",
                device_integrity=device_recognition_verdict,
                app_integrity=app_recognition_verdict
            )

            return {
                "device_integrity": device_recognition_verdict,
                "app_integrity": app_recognition_verdict,
                "account_details": account_details,
                "verified": True
            }

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                logger.error("Invalid integrity token", status_code=e.response.status_code)
                raise VeriphyException("Invalid integrity token provided", status_code=400)
            elif e.response.status_code == 403:
                logger.error("Google Play Integrity API access denied", status_code=e.response.status_code)
                raise VeriphyException("Play Integrity API access denied", status_code=403)
            else:
                logger.error("Google Play Integrity API error", status_code=e.response.status_code)
                raise VeriphyException("Play Integrity verification failed", status_code=502)

        except httpx.RequestError as e:
            logger.error("Google Play Integrity network error", error=str(e))
            raise VeriphyException("Play Integrity service unavailable", status_code=502)

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()