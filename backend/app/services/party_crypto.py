"""Field-level encryption for bank account numbers - ported from domain/crypto.ts.

PRODUCTION NOTE (carried over from the Node source): the data-encryption key is
derived from a single shared secret, so every row shares one key and rotation
means re-encrypting the table. Swap the key source for real KMS/Vault later;
keep this module's interface and the versioned "v1." envelope prefix so both
schemes can coexist during migration.

Ciphertext layout: v1.<iv>.<authTag>.<ciphertext>, each part base64url (no
padding, matching Node's Buffer.toString("base64url")).
"""

from __future__ import annotations

import base64
import functools
import hmac
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

VERSION = "v1"
KEY_BYTES = 32  # AES-256
IV_BYTES = 12  # 96-bit nonce, GCM-recommended size

HKDF_SALT = b"axon-erp/party/bank-account/v1"
HKDF_INFO = b"party.bank_accounts.account_number"


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


@functools.lru_cache(maxsize=4)
def _derive_key(secret: str) -> bytes:
    if len(secret) < 16:
        raise ValueError("Encryption secret is too short to derive a key from — use at least 16 characters")
    return HKDF(algorithm=hashes.SHA256(), length=KEY_BYTES, salt=HKDF_SALT, info=HKDF_INFO).derive(secret.encode("utf-8"))


def seal(plaintext: str, secret: str) -> str:
    iv = os.urandom(IV_BYTES)
    aesgcm = AESGCM(_derive_key(secret))
    # Python's AESGCM appends the 16-byte auth tag to the ciphertext.
    sealed = aesgcm.encrypt(iv, plaintext.encode("utf-8"), None)
    ciphertext, tag = sealed[:-16], sealed[-16:]
    return ".".join([VERSION, _b64(iv), _b64(tag), _b64(ciphertext)])


def open_(envelope: str, secret: str) -> str:
    parts = envelope.split(".")
    if len(parts) != 4 or parts[0] != VERSION:
        raise ValueError(f"Unsupported bank-account ciphertext envelope: {parts[0] if parts else '(empty)'}")
    _, iv_b64, tag_b64, ciphertext_b64 = parts
    aesgcm = AESGCM(_derive_key(secret))
    iv = _unb64(iv_b64)
    sealed = _unb64(ciphertext_b64) + _unb64(tag_b64)
    return aesgcm.decrypt(iv, sealed, None).decode("utf-8")


def mask_account_number(account_number: str) -> str:
    digits = account_number.replace(" ", "")
    return f"****{digits[-4:]}"


def last_four(account_number: str) -> str:
    return account_number.replace(" ", "")[-4:]


def matches_sealed(candidate: str, envelope: str, secret: str) -> bool:
    try:
        stored = open_(envelope, secret)
    except Exception:
        return False
    return hmac.compare_digest(stored.encode("utf-8"), candidate.encode("utf-8"))
