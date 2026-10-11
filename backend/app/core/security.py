"""Access + rotating refresh tokens, password hashing, TOTP MFA.

Merged from backend_py/app/services/tokens.py + password.py + totp.py -
those three files had no Flask coupling beyond `from app.extensions import db`
/ `db.session`, which becomes `from app.core.db import session`. Logic,
constants (argon2id memory_cost=19456/time_cost=2/parallelism=1, HS256 JWT,
TOTP window=1) and claim shapes are unchanged so existing password hashes
and any token either app issues stay mutually verifiable during side-by-side
testing.
"""

from __future__ import annotations

import hashlib
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import settings
from app.core.db import session
from app.core.errors import rule_violation, unauthorized
from app.models.session import Session as SessionModel

# ---- JWT access + refresh tokens ------------------------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc)


def random_token(num_bytes: int = 32) -> str:
    return secrets.token_urlsafe(num_bytes)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def sign_access_token(
    *,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    email: str,
    name: str,
    roles: list[str],
    permissions: list[str],
    scopes: list[str],
    session_id: uuid.UUID,
    warehouse_ids: list[str] | None = None,
    factory_ids: list[str] | None = None,
) -> str:
    now = _now()
    claims = {
        "sub": str(user_id),
        "tid": str(tenant_id),
        "email": email,
        "name": name,
        "roles": roles,
        "perms": permissions,
        "scopes": scopes,
        "sid": str(session_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=settings.access_token_ttl)).timestamp()),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "jti": str(uuid.uuid4()),
    }
    # Omitted entirely (rather than null) when unrestricted, matching the
    # actor dict's None-means-unrestricted convention (app/core/auth.py).
    if warehouse_ids is not None:
        claims["whIds"] = warehouse_ids
    if factory_ids is not None:
        claims["facIds"] = factory_ids
    return jwt.encode(claims, settings.jwt_secret, algorithm="HS256")


def verify_access_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            leeway=5,
        )
    except jwt.PyJWTError as exc:
        raise unauthorized("Invalid or expired access token", code="INVALID_TOKEN") from exc


def create_session(*, user_id: uuid.UUID, tenant_id: uuid.UUID, ip: str | None, user_agent: str | None) -> tuple[str, SessionModel]:
    raw = random_token()
    sess = SessionModel(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_id=user_id,
        refresh_token_hash=hash_token(raw),
        expires_at=_now() + timedelta(seconds=settings.refresh_token_ttl),
        ip=ip,
        user_agent=user_agent,
    )
    session.add(sess)
    session.flush()
    return raw, sess


def revoke_all_sessions_for_user(user_id: uuid.UUID) -> None:
    SessionModel.query.filter(SessionModel.user_id == user_id, SessionModel.revoked_at.is_(None)).update(
        {"revoked_at": _now()}, synchronize_session=False
    )


def rotate_session(raw_refresh_token: str, *, ip: str | None, user_agent: str | None) -> tuple[str, SessionModel]:
    """Rotating refresh tokens: reuse of an already-rotated token revokes ALL sessions for that user."""
    token_hash = hash_token(raw_refresh_token)
    sess = SessionModel.query.filter_by(refresh_token_hash=token_hash).first()
    if sess is None:
        raise unauthorized("Invalid refresh token", code="REFRESH_TOKEN_INVALID")

    if sess.revoked_at is not None:
        revoke_all_sessions_for_user(sess.user_id)
        session.commit()
        raise unauthorized("Refresh token was already used - all sessions revoked", code="REFRESH_TOKEN_REUSED")

    if sess.expires_at < _now():
        sess.revoked_at = _now()
        session.commit()
        raise unauthorized("Refresh token has expired", code="REFRESH_TOKEN_EXPIRED")

    new_raw = random_token()
    new_session = SessionModel(
        id=uuid.uuid4(),
        tenant_id=sess.tenant_id,
        user_id=sess.user_id,
        refresh_token_hash=hash_token(new_raw),
        expires_at=_now() + timedelta(seconds=settings.refresh_token_ttl),
        ip=ip,
        user_agent=user_agent,
    )
    session.add(new_session)
    session.flush()

    sess.revoked_at = _now()
    sess.rotated_to = new_session.id

    return new_raw, new_session


def revoke_session_by_refresh_token(raw_refresh_token: str) -> None:
    token_hash = hash_token(raw_refresh_token)
    sess = SessionModel.query.filter_by(refresh_token_hash=token_hash).first()
    if sess is not None and sess.revoked_at is None:
        sess.revoked_at = _now()


# ---- Argon2id password hashing --------------------------------------------

_hasher = PasswordHasher(memory_cost=19_456, time_cost=2, parallelism=1)

_COMMON_PASSWORDS = {
    "password",
    "password1",
    "12345678",
    "qwertyuiop",
    "letmein",
    "admin123",
    "welcome1",
    "changeme",
    "axonerp123",
}


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, stored: str) -> bool:
    try:
        return _hasher.verify(stored, plain)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def assert_password_meets_policy(password: str, policy, email: str | None = None) -> None:
    """`policy` is an AuthPolicy model instance (or anything with the same attrs)."""
    errors: list[dict] = []

    if len(password) < policy.password_min_length:
        errors.append({"field": "password", "message": f"Must be at least {policy.password_min_length} characters"})
    if policy.password_require_number and not re.search(r"\d", password):
        errors.append({"field": "password", "message": "Must contain at least one digit"})
    if policy.password_require_symbol and not re.search(r"[^A-Za-z0-9]", password):
        errors.append({"field": "password", "message": "Must contain at least one symbol"})
    if policy.password_require_mixed_case and not (re.search(r"[a-z]", password) and re.search(r"[A-Z]", password)):
        errors.append({"field": "password", "message": "Must mix upper and lower case letters"})
    if password.lower() in _COMMON_PASSWORDS:
        errors.append({"field": "password", "message": "This password is too common"})
    if email:
        local_part = email.split("@")[0].lower()
        if local_part and local_part in password.lower():
            errors.append({"field": "password", "message": "Must not contain your email name"})

    if errors:
        raise rule_violation(
            "Password does not meet the tenant password policy",
            code="PASSWORD_POLICY_VIOLATION",
            meta={"errors": errors},
        )


# ---- TOTP (RFC 6238) MFA ---------------------------------------------------


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def build_otpauth_url(secret: str, account_email: str) -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(name=account_email, issuer_name=settings.mfa_issuer)


def verify_totp(secret: str, code: str) -> bool:
    return pyotp.totp.TOTP(secret).verify(code, valid_window=1)
