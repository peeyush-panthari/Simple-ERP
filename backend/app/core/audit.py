"""Audit log writes with sensitive-field redaction.

`audit()` adds a row to the session without committing; the caller's later
`session.commit()` is what makes "state change + audit row" one atomic transaction.
"""

from __future__ import annotations

import uuid

from app.core.db import session
from app.models.audit_log import AuditLog

_SENSITIVE_KEYS = {"password", "password_hash", "mfa_secret", "token", "refresh_token", "access_token", "bank_account", "bank_details"}


def _redact(meta: dict | None) -> dict:
    if not meta:
        return {}
    return {k: ("[REDACTED]" if k.lower() in _SENSITIVE_KEYS else v) for k, v in meta.items()}


def audit(
    *,
    tenant_id: uuid.UUID | None,
    actor_id: uuid.UUID | None,
    actor_email: str | None,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    reason: str | None = None,
    correlation_id: str | None = None,
    meta: dict | None = None,
) -> None:
    entry = AuditLog(
        tenant_id=tenant_id,
        actor_id=actor_id,
        actor_email=actor_email,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        reason=reason,
        correlation_id=correlation_id,
        meta=_redact(meta),
    )
    session.add(entry)


def read_audit_trail(*, tenant_id: uuid.UUID, entity_type: str | None = None, entity_id: str | None = None, limit: int = 50):
    query = AuditLog.query.filter(AuditLog.tenant_id == tenant_id)
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    if entity_id:
        query = query.filter(AuditLog.entity_id == entity_id)
    return query.order_by(AuditLog.created_at.desc()).limit(limit).all()
