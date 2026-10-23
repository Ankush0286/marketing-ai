import base64
import hashlib
from functools import lru_cache
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


class EncryptionError(Exception):
    """Raised when encryption or decryption fails."""
    pass


@lru_cache
def _get_fernet_cipher() -> Fernet:
    """
    Initializes a Fernet cipher instance using the master SECRET_KEY.
    Ensures the key is normalized into a valid 32-byte URL-safe base64 string.
    """
    raw_key = settings.SECRET_KEY.encode("utf-8")

    # If the user provides an arbitrary text secret, derive a consistent 32-byte key via SHA256
    derived_bytes = hashlib.sha256(raw_key).digest()
    url_safe_key = base64.urlsafe_b64encode(derived_bytes)
    
    return Fernet(url_safe_key)


def encrypt_value(plain_text: str | None) -> str | None:
    """
    Encrypts a plaintext string into a URL-safe base64 ciphertext.
    Returns None if input is None or empty.
    """
    if not plain_text:
        return None
    try:
        cipher = _get_fernet_cipher()
        encrypted_bytes = cipher.encrypt(plain_text.encode("utf-8"))
        return encrypted_bytes.decode("utf-8")
    except Exception as exc:
        raise EncryptionError(f"Failed to encrypt credential: {exc}") from exc


def decrypt_value(cipher_text: str | None) -> str | None:
    """
    Decrypts a base64 ciphertext back into original plaintext.
    Returns None if input is None or empty.
    """
    if not cipher_text:
        return None
    try:
        cipher = _get_fernet_cipher()
        decrypted_bytes = cipher.decrypt(cipher_text.encode("utf-8"))
        return decrypted_bytes.decode("utf-8")
    except InvalidToken:
        raise EncryptionError("Invalid token or incorrect SECRET_KEY provided.")
    except Exception as exc:
        raise EncryptionError(f"Failed to decrypt credential: {exc}") from exc


def generate_master_key() -> str:
    """Utility helper to generate a secure random 32-byte key for .env."""
    return Fernet.generate_key().decode("utf-8")