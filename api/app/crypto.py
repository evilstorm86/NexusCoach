"""Symmetric encryption for secrets we store on a user's behalf.

ponytail: Fernet from `cryptography` rather than a hand-rolled scheme or a KMS. It is
authenticated AES-128-CBC with a sane key format, and it ships with a library we now
need anyway. Ceiling: one key for everything, rotated by re-encrypting the table — if
per-tenant keys or an HSM ever matter, this is the seam to change.
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from .config import settings


def _key() -> bytes:
    if settings.secrets_key:
        return settings.secrets_key.encode()
    # Derive from JWT_SECRET so a dev instance works with no extra config. Set
    # SECRETS_KEY in production: rotating JWT_SECRET would otherwise orphan every
    # stored secret.
    digest = hashlib.sha256(f"nexuscoach.secrets:{settings.jwt_secret}".encode()).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt(plaintext: str) -> str:
    return Fernet(_key()).encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str | None:
    """None when the value can't be read — a rotated key, not a crash."""
    try:
        return Fernet(_key()).decrypt(ciphertext.encode()).decode()
    except (InvalidToken, ValueError):
        return None


def mask(value: str) -> str:
    """Show enough to recognise a key, never enough to use it."""
    return f"…{value[-4:]}" if len(value) > 8 else "…"
