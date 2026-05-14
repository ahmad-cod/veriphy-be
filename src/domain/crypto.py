import base64
import hashlib
import hmac
from cryptography.fernet import Fernet
import aioboto3
from botocore.exceptions import ClientError

from src.core.config import settings
import structlog

logger = structlog.get_logger()

class PIICryptoService:
    def __init__(self):
        if settings.ENVIRONMENT == "local":
            local_dek = settings.LOCAL_DEK
            if local_dek is None:
                raise RuntimeError("LOCAL_DEK must be configured for local encryption.")
            self.local_dek = local_dek.get_secret_value().encode()
        else:
            self.local_dek = None

    def hash_pii(self, plaintext: str) -> str:
        secret = settings.BVN_HASH_PEPPER.get_secret_value().encode()
        return hmac.new(secret, plaintext.encode("utf-8"), hashlib.sha256).hexdigest()

    async def encrypt_data(self, plaintext: str, context: dict) -> str:
        """Envelope Encryption: KMS generates DEK -> Encrypt data -> Store encrypted DEK + Ciphertext"""
        if settings.ENVIRONMENT == "local":
            if self.local_dek is None:
                raise ValueError("Encryption key (DEK) has not been initialized.")
            f = Fernet(self.local_dek)
            ciphertext = f.encrypt(plaintext.encode()).decode()
            return f"local-env:{ciphertext}"

        session = aioboto3.Session()
        async with session.client(   # pyright: ignore[reportGeneralTypeIssues]
            "kms",
            region_name="eu-west-1"
        ) as kms:
            try:
                response = await kms.generate_data_key(
                    KeyId=settings.AWS_KMS_KEY_ID,
                    NumberOfBytes=32,
                    EncryptionContext=context,
                )

                dek_plaintext = base64.urlsafe_b64encode(response["Plaintext"])
                f = Fernet(dek_plaintext)
                ciphertext = f.encrypt(plaintext.encode()).decode()

                dek_ciphertext = base64.b64encode(response["CiphertextBlob"]).decode()
                return f"v1:{dek_ciphertext}:{ciphertext}"
            except ClientError as e:
                logger.error("KMS GenerateDataKey failed", error=str(e))
                raise RuntimeError("Failed to secure PII payload") from e

    async def decrypt_data(self, encrypted_payload: str, context: dict) -> str:
        """Decrypts the DEK via KMS, then decrypts the local ciphertext."""
        if encrypted_payload.startswith("local-env:"):
            if self.local_dek is None:
                raise ValueError("Encryption key (DEK) has not been initialized.")
            f = Fernet(self.local_dek)
            return f.decrypt(encrypted_payload.split(":", 1)[1].encode()).decode()

        parts = encrypted_payload.split(":", 2)
        if len(parts) != 3 or parts[0] != "v1":
            raise ValueError("Invalid encrypted payload format")

        dek_ciphertext = base64.b64decode(parts[1])
        ciphertext = parts[2]

        session = aioboto3.Session()
        async with session.client(   # pyright: ignore[reportGeneralTypeIssues]
            "kms",
            region_name="eu-west-1"
        ) as kms:
            try:
                # 1. Ask KMS to decrypt the DEK
                response = await kms.decrypt(
                    CiphertextBlob=dek_ciphertext,
                    EncryptionContext=context,
                )
                
                # 2. Use the decrypted DEK to decrypt the payload
                dek_plaintext = base64.urlsafe_b64encode(response['Plaintext'])
                f = Fernet(dek_plaintext)
                return f.decrypt(ciphertext.encode()).decode()
            except ClientError as e:
                logger.error("KMS Decrypt failed", error=str(e))
                raise RuntimeError("Failed to access PII payload") from e