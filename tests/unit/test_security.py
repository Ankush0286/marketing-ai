import pytest

from app.core.security import (
    EncryptionError,
    decrypt_token,
    encrypt_token,
    generate_master_key,
)


def test_encrypt_decrypt_roundtrip():
    original = "ghp_super_secret_oauth_token_12345"
    encrypted = encrypt_token(original)

    assert encrypted is not None
    assert encrypted != original

    decrypted = decrypt_token(encrypted)
    assert decrypted == original


def test_encrypt_decrypt_none_and_empty():
    assert encrypt_token(None) is None
    assert decrypt_token(None) is None
    assert encrypt_token("") == ""
    assert decrypt_token("") == ""


def test_decrypt_invalid_ciphertext_raises_encryption_error():
    with pytest.raises(EncryptionError):
        decrypt_token("not-a-valid-fernet-token")


def test_generate_master_key():
    key = generate_master_key()
    assert isinstance(key, str)
    assert len(key) == 44  # Base64 encoded 32 bytes
