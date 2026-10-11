"""Foundation > Email Config: one setup per kind of email.

GET    /api/v1/email-config                    every kind with its own mailbox, switches and Cc/Bcc
PUT    /api/v1/email-config/{key}              save ONE kind (purchase-order.issued, invoice.issued, logistics.rfq, ...)
DELETE /api/v1/email-config/{key}              back to the default for that kind
POST   /api/v1/email-config/{key}/test         send a test through that kind's saved mailbox
POST   /api/v1/email-config/{key}/copy-from    reuse another kind's mailbox (password included) without retyping it

The SMTP password is write-only: accepted on PUT (omit to keep the saved one, "" to remove it) and never returned,
logged or written to the audit trail.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from app.core.audit import audit
from app.core.auth import Actor, require_permission
from app.core.db import session
from app.services import email_config_repo

router = APIRouter(prefix="/api/v1/email-config", tags=["email-config"])


class PurposeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sendEnabled: bool = True
    useOwnMailbox: bool = False
    smtpHost: str = Field(default="", max_length=253)
    smtpPort: int = Field(default=587, ge=1, le=65535)
    security: str = "starttls"
    smtpUser: str = Field(default="", max_length=254)
    smtpPassword: str | None = Field(default=None, max_length=500)
    fromName: str = Field(default="", max_length=120)
    fromEmail: str = Field(default="", max_length=254)
    replyTo: str | None = Field(default=None, max_length=254)
    cc: list[str] = Field(default_factory=list, max_length=20)
    bcc: list[str] = Field(default_factory=list, max_length=20)


class TestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    to: str = Field(max_length=254)


class CopyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sourceKey: str = Field(max_length=100)


def _one(tenant_id, key: str) -> dict:
    purpose = email_config_repo._require_key(key)
    return email_config_repo.purpose_to_api(purpose, email_config_repo.get_row(tenant_id, key))


@router.get("")
def get_email_config(actor: Actor = Depends(require_permission("email_config:read"))):
    return email_config_repo.to_api(actor["tenant_id"])


@router.put("/{key}")
def put_email_config(key: str, body: PurposeBody, actor: Actor = Depends(require_permission("email_config:write"))):
    tenant_id = actor["tenant_id"]
    row = email_config_repo.save(tenant_id, key, actor_id=actor["user_id"], data=body.model_dump())
    audit(
        tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="email-config.updated", entity_type="email-config", entity_id=key,
        # What changed hands - never the password itself.
        meta={"purpose": key, "sendEnabled": row.send_enabled, "useOwnMailbox": row.enabled, "smtpHost": row.smtp_host, "smtpPort": row.smtp_port, "security": row.security,
              "smtpUser": row.smtp_user, "fromEmail": row.from_email, "passwordChanged": body.smtpPassword is not None},
    )
    session.commit()
    return _one(tenant_id, key)


@router.delete("/{key}")
def delete_email_config(key: str, actor: Actor = Depends(require_permission("email_config:write"))):
    tenant_id = actor["tenant_id"]
    email_config_repo.reset(tenant_id, key)
    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="email-config.reset", entity_type="email-config", entity_id=key, meta={"purpose": key})
    session.commit()
    return _one(tenant_id, key)


@router.post("/{key}/test")
def post_test_email(key: str, body: TestBody, actor: Actor = Depends(require_permission("email_config:write"))):
    tenant_id = actor["tenant_id"]
    result = email_config_repo.send_test(tenant_id, key, body.to.strip())
    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="email-config.tested", entity_type="email-config", entity_id=key, meta={"purpose": key, "to": body.to.strip(), "ok": result["ok"]})
    session.commit()
    return {**result, "purpose": _one(tenant_id, key)}


@router.post("/{key}/copy-from")
def post_copy_mailbox(key: str, body: CopyBody, actor: Actor = Depends(require_permission("email_config:write"))):
    tenant_id = actor["tenant_id"]
    email_config_repo.copy_mailbox(tenant_id, key, body.sourceKey, actor_id=actor["user_id"])
    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="email-config.mailbox-copied", entity_type="email-config", entity_id=key, meta={"purpose": key, "from": body.sourceKey})
    session.commit()
    return _one(tenant_id, key)
