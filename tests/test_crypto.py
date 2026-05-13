import pytest

from src.domain.crypto import PIICryptoService


@pytest.mark.asyncio
async def test_local_encryption_cycle_works():
    crypto = PIICryptoService()
    plaintext = "01234567890"
    context = {"purpose": "test", "entity": "merchant"}

    encrypted = await crypto.encrypt_data(plaintext, context)
    assert encrypted.startswith("local-env:")

    decrypted = await crypto.decrypt_data(encrypted, context)
    assert decrypted == plaintext


def test_hash_pii_is_deterministic():
    crypto = PIICryptoService()
    first = crypto.hash_pii("12345678901")
    second = crypto.hash_pii("12345678901")
    assert first == second
    assert len(first) == 64
