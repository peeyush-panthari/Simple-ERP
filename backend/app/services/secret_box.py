"""Encrypts small secrets stored in the database (an SMTP password) with AES-256-GCM.

Same envelope as party_crypto (`v1.<iv>.<tag>.<ciphertext>`, base64url) but its own HKDF salt/info, so a bank
account ciphertext can never be opened as a mailbox password or the reverse. The key comes from
ENCRYPTION_SECRET; rotating that secret means the mail password has to be entered again (nothing else breaks).
"""

from __future__ import annotations

import base64
import functools
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

VERSION = "v1"
_SALT = b"simple-erp/secret-box/v1"


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


@functools.lru_cache(maxsize=8)
def _key(secret: str, purpose: str) -> bytes:
    if len(secret) < 16:
        raise ValueError("Encryption secret is too short - use at least 16 characters")
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=_SALT, info=purpose.encode()).derive(secret.encode("utf-8"))


def seal(plaintext: str, secret: str, purpose: str) -> str:
    iv = os.urandom(12)
    sealed = AESGCM(_key(secret, purpose)).encrypt(iv, plaintext.encode("utf-8"), None)
    return ".".join([VERSION, _b64(iv), _b64(sealed[-16:]), _b64(sealed[:-16])])


def unseal(envelope: str, secret: str, purpose: str) -> str:
    parts = envelope.split(".")
    if len(parts) != 4 or parts[0] != VERSION:
        raise ValueError("Unsupported secret envelope")
    _, iv, tag, ciphertext = parts
    return AESGCM(_key(secret, purpose)).decrypt(_unb64(iv), _unb64(ciphertext) + _unb64(tag), None).decode("utf-8")
