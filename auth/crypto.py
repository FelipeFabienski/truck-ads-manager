from __future__ import annotations

import os

from cryptography.fernet import Fernet

# Fallback key for dev/test — override via TOKEN_ENCRYPTION_KEY in production
_DEV_KEY = b"jPFImbFBwGaWtfb9FxPX7-l0gWIf43N6B-fMFXJ_4pM="


def _fernet() -> Fernet:
    raw = os.getenv("TOKEN_ENCRYPTION_KEY")
    key = raw.encode() if raw else _DEV_KEY
    return Fernet(key)


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode()).decode()
