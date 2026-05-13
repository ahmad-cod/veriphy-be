import base64
import os
import json
from cryptography.fernet import Fernet
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
import aioboto3
from botocore.exceptions import ClientError

from src.core.config import settings
import structlog

logger = structlog.get_logger()

class PIICryptoService:
    def __init__(self):
        # Tuned for web concurrency (48 MiB memory, lower parallelism)
        self.ph = PasswordHasher(
            time_cost=2, 
            memory_cost=49152, 
            parallelism=2,
            hash_len=32,
            salt_len=16
        )
        
        # Local fallback key for local environment
        self.local_dek = Fernet.generate_key() if settings.ENVIRONMENT == "local" else None

    def hash_pii(self, plaintext: str) -> str:
        peppered_text = f"{plaintext}{settings.BVN_HASH_PEPPER.get_secret_value()}"
        return self.ph.hash(peppered_text)

    async def encrypt_data(self, plaintext: str, context: dict) -> str:
        """Envelope Encryption: KMS generates DEK -> Encrypt data -> Store encrypted DEK + Ciphertext"""
        if settings.ENVIRONMENT == "local":
            if self.local_dek is None:
                raise ValueError("Encryption key (DEK) has not been initialized.")
            f = Fernet(self.local_dek)
            ciphertext = f.encrypt(plaintext.encode()).decode()
            return f"local-env:{ciphertext}"

        session = aioboto3.Session()
        async with session.client('kms', region_name='eu-west-1') as kms:
            try:
                # 1. Ask KMS for a Data Encryption Key (DEK)
                response = await kms.generate_data_key(
                    KeyId=settings.AWS_KMS_KEY_ID,
                    NumberOfBytes=32,
                    EncryptionContext=context
                )
                
                # 2. Encrypt the payload locally using the plaintext DEK
                dek_plaintext = base64.urlsafe_b64encode(response['Plaintext'])
                f = Fernet(dek_plaintext)
                ciphertext = f.encrypt(plaintext.encode()).decode()
                
                # 3. Store the KMS-encrypted DEK and the Ciphertext together
                dek_ciphertext = base64.b64encode(response['CiphertextBlob']).decode()
                
                # Format: [version]:[encrypted_dek]:[ciphertext]
                return f"v1:{dek_ciphertext}:{ciphertext}"
                
            except ClientError as e:
                logger.error("KMS GenerateDataKey failed", error=str(e))
                raise RuntimeError("Failed to secure PII payload")

    async def decrypt_data(self, encrypted_payload: str, context: dict) -> str:
        """Decrypts the DEK via KMS, then decrypts the local ciphertext."""
        if encrypted_payload.startswith("local-env:"):
            if self.local_dek is None:
                raise ValueError("Encryption key (DEK) has not been initialized.")
            f = Fernet(self.local_dek)
            return f.decrypt(encrypted_payload.split(":")[1].encode()).decode()

        parts = encrypted_payload.split(":")
        if len(parts) != 3 or parts[0] != "v1":
            raise ValueError("Invalid encrypted payload format")
            
        dek_ciphertext = base64.b64decode(parts[1])
        ciphertext = parts[2]

        session = aioboto3.Session()
        async with session.client('kms', region_name='eu-west-1') as kms:
            try:
                # 1. Ask KMS to decrypt the DEK
                response = await kms.decrypt(
                    CiphertextBlob=dek_ciphertext,
                    EncryptionContext=context
                )
                
                # 2. Use the decrypted DEK to decrypt the payload
                dek_plaintext = base64.urlsafe_b64encode(response['Plaintext'])
                f = Fernet(dek_plaintext)
                return f.decrypt(ciphertext.encode()).decode()
                
            except ClientError as e:
                logger.error("KMS Decrypt failed", error=str(e))
                raise RuntimeError("Failed to access PII payload")