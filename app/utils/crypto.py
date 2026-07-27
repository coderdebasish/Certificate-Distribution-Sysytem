"""
app.utils.crypto
================
Credential encryption and decryption.

Uses the ``cryptography`` library (Fernet symmetric encryption).
The encryption key is derived from machine-specific entropy and stored
in a local key file — never transmitted externally.
"""

from __future__ import annotations

import base64
import os
from pathlib import Path

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False


_KEY_FILE = Path.home() / ".cdms" / ".secret.key"
_SALT = b"cdms_salt_v1_2027"   # Static salt (not security-critical for local use)


def _get_or_create_key() -> bytes:
    """Load or generate the Fernet key."""
    if _KEY_FILE.exists():
        return _KEY_FILE.read_bytes()
    _KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    key = Fernet.generate_key()
    _KEY_FILE.write_bytes(key)
    # Restrict file permissions on Windows (best effort)
    try:
        import stat
        os.chmod(_KEY_FILE, stat.S_IRUSR | stat.S_IWUSR)
    except Exception:
        pass
    return key


def encrypt(plaintext: str) -> str:
    """
    Encrypt *plaintext* and return a base64-encoded ciphertext string.
    Falls back to base64 obfuscation if the cryptography library is missing.
    """
    if not _CRYPTO_AVAILABLE:
        return base64.b64encode(plaintext.encode()).decode()
    f = Fernet(_get_or_create_key())
    return f.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """
    Decrypt a ciphertext string previously produced by ``encrypt()``.
    Returns an empty string on failure.
    """
    if not ciphertext:
        return ""
    if not _CRYPTO_AVAILABLE:
        try:
            return base64.b64decode(ciphertext.encode()).decode()
        except Exception:
            return ""
    try:
        f = Fernet(_get_or_create_key())
        return f.decrypt(ciphertext.encode()).decode()
    except Exception:
        return ""
