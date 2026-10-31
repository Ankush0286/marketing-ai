import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


class EncryptionError(Exception):
    """Raised when encryption or decryption fails."""

@lru_cache
def _get_fernet_cipher() -> Fernet:
    """
    Initializes a Fernet cipher instance using settings.SECRET_KEY.
    Directly uses valid 32-byte base64 keys, or derives one via SHA-256 for passphrases.
    """
    raw_key = settings.SECRET_KEY.get_secret_value().strip().encode("utf-8")

    try:
        if len(raw_key) == 44 and len(base64.urlsafe_b64decode(raw_key)) == 32:
            return Fernet(raw_key)
    except Exception:
        pass

    derived_bytes = hashlib.sha256(raw_key).digest()
    url_safe_key = base64.urlsafe_b64encode(derived_bytes)
    return Fernet(url_safe_key)


def encrypt_token(plain_text: str | None) -> str | None:
    """
    Encrypts a plaintext string into URL-safe base64 ciphertext.
    Returns None if input is None.
    """
    if plain_text is None:
        return None
    if plain_text == "":
        return ""
    try:
        cipher = _get_fernet_cipher()
        encrypted_bytes = cipher.encrypt(plain_text.encode("utf-8"))
        return encrypted_bytes.decode("utf-8")
    except Exception as exc:
        raise EncryptionError(f"Failed to encrypt credential: {exc}") from exc


def decrypt_token(cipher_text: str | None) -> str | None:
    """
    Decrypts a base64 ciphertext back into original plaintext.
    Returns None if input is None.
    """
    if cipher_text is None:
        return None
    if cipher_text == "":
        return ""
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
