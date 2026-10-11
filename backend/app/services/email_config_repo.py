"""Foundation > Email Config: one outgoing setup per kind of email (purchase orders, logistics quotation requests,
customer invoices, ...), each with its own mailbox, sender, Cc/Bcc and on/off switches.

`resolve()` is what the notification worker/request path calls to decide which mailbox a message leaves through:
that kind's saved config when its own mailbox is switched on, else the deployment's SMTP_* environment settings (the
old behaviour, so nothing changes until someone saves and enables a config).
"""

from __future__ import annotations

import ipaddress
import re
import uuid
from datetime import datetime, timezone

from app.core.config import settings
from app.core.db import session
from app.core.errors import not_found, rule_violation
from app.models.email_config import EmailConfig
from app.services import notification_transport, secret_box
from app.services.notification_transport import MailSettings

_SECRET_PURPOSE = "email-config/smtp-password"
_EMAIL_RE = re.compile(r"^[^@\s,;<>]+@[^@\s,;<>]+\.[^@\s,;<>]+$")

# Every email the platform sends, keyed by notification template key. Order = order on the screen.
PURPOSES: list[dict] = [
    {"key": "purchase-order.issued", "label": "Purchase orders", "description": "Sent to the vendor when a purchase order is issued or re-sent."},
    {"key": "purchase-rfq.issued", "label": "Purchase quotation requests (RFQ)", "description": "Sent to each invited vendor when Purchase asks for a quotation on an approved requisition."},
    {"key": "logistics.rfq", "label": "Logistics quotation requests (RFQ)", "description": "Sent to each invited carrier when a transport request goes out for quotation."},
    {"key": "invoice.issued", "label": "Customer invoices", "description": "Sent to the customer when a sales invoice is generated."},
    {"key": "logistics.pre-dispatch", "label": "Dispatch notices", "description": "Sent to the source warehouse ahead of a carrier collection."},
    {"key": "user.invitation", "label": "User invitations", "description": "Sent when a new user is created without a password."},
]
PURPOSE_KEYS = {p["key"] for p in PURPOSES}

PRESETS = {
    "gmail": {"label": "Gmail / Google Workspace", "smtpHost": "smtp.gmail.com", "smtpPort": 587, "security": "starttls"},
    "outlook": {"label": "Microsoft 365 / Outlook", "smtpHost": "smtp.office365.com", "smtpPort": 587, "security": "starttls"},
}


def get_row(tenant_id: uuid.UUID, key: str) -> EmailConfig | None:
    return session.query(EmailConfig).filter_by(tenant_id=tenant_id, purpose_key=key).first()


def _require_key(key: str) -> dict:
    for p in PURPOSES:
        if p["key"] == key:
            return p
    raise not_found(f"Email type {key}")


def _from_header(row: EmailConfig) -> str:
    name = row.from_name.replace('"', "").replace("\r", "").replace("\n", "").strip()
    return f'"{name}" <{row.from_email}>' if name else row.from_email


def _is_local_host(host: str) -> bool:
    h = (host or "").strip().lower()
    if h in ("localhost", "mailpit") or h.endswith(".localhost"):
        return True
    try:
        ip = ipaddress.ip_address(h)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_unspecified


def purpose_to_api(purpose: dict, row: EmailConfig | None) -> dict:
    return {
        **purpose,
        "configured": row is not None,
        "sendEnabled": bool(row.send_enabled) if row else True,
        "useOwnMailbox": bool(row and row.enabled),
        "smtpHost": row.smtp_host if row else "",
        "smtpPort": row.smtp_port if row else 587,
        "security": row.security if row else "starttls",
        "smtpUser": row.smtp_user if row else "",
        "passwordSet": bool(row and row.smtp_password_sealed),
        "fromName": row.from_name if row else "",
        "fromEmail": row.from_email if row else "",
        "replyTo": (row.reply_to if row else None) or "",
        "cc": list(row.cc or []) if row else [],
        "bcc": list(row.bcc or []) if row else [],
        "lastTest": {
            "at": row.last_test_at.isoformat() if row and row.last_test_at else None,
            "ok": row.last_test_ok if row else None,
            "error": row.last_test_error if row else None,
        },
        "updatedAt": row.updated_at.isoformat() if row and row.updated_at else None,
    }


def to_api(tenant_id: uuid.UUID) -> dict:
    rows = {r.purpose_key: r for r in session.query(EmailConfig).filter_by(tenant_id=tenant_id).all()}
    env = notification_transport.env_mail_settings()
    return {
        "purposes": [purpose_to_api(p, rows.get(p["key"])) for p in PURPOSES],
        "presets": [{"key": k, **v} for k, v in PRESETS.items()],
        "environment": {"host": env.host, "port": env.port, "security": env.security, "from": env.from_header, "isLocal": _is_local_host(env.host)},
    }


def _clean_emails(values: list[str] | None, what: str) -> list[str]:
    out: list[str] = []
    for raw in values or []:
        v = (raw or "").strip()
        if not v:
            continue
        if not _EMAIL_RE.match(v):
            raise rule_violation(f'"{v}" is not a valid email address ({what})', code="EMAIL_CONFIG_INVALID")
        if v.lower() not in [o.lower() for o in out]:
            out.append(v)
    return out


def save(tenant_id: uuid.UUID, key: str, *, actor_id, data: dict) -> EmailConfig:
    """Validates and upserts ONE kind's setup. `data["smtpPassword"]`: None keeps the saved one, "" removes it,
    anything else replaces it."""
    _require_key(key)
    host = (data.get("smtpHost") or "").strip()
    user = (data.get("smtpUser") or "").strip()
    from_email = (data.get("fromEmail") or "").strip()
    reply_to = (data.get("replyTo") or "").strip() or None
    if data.get("security") not in ("none", "starttls", "ssl"):
        raise rule_violation("Security must be none, starttls or ssl", code="EMAIL_CONFIG_INVALID")
    if not (1 <= int(data.get("smtpPort") or 0) <= 65535):
        raise rule_violation("SMTP port must be between 1 and 65535", code="EMAIL_CONFIG_INVALID")
    if from_email and not _EMAIL_RE.match(from_email):
        raise rule_violation(f'"{from_email}" is not a valid sender address', code="EMAIL_CONFIG_INVALID")
    if reply_to and not _EMAIL_RE.match(reply_to):
        raise rule_violation(f'"{reply_to}" is not a valid reply-to address', code="EMAIL_CONFIG_INVALID")
    if host and settings.app_env == "production" and _is_local_host(host):
        raise rule_violation("In production the SMTP host must be a public mail server, not a local or private address", code="EMAIL_CONFIG_INVALID")
    if any(ch in host + user + (data.get("fromName") or "") for ch in "\r\n"):
        raise rule_violation("Values cannot contain line breaks", code="EMAIL_CONFIG_INVALID")
    if data.get("useOwnMailbox") and not (host and from_email):
        raise rule_violation("Using its own mailbox needs an SMTP server and a sender address", code="EMAIL_CONFIG_INVALID")

    row = get_row(tenant_id, key)
    if row is None:
        row = EmailConfig(tenant_id=tenant_id, purpose_key=key)
        session.add(row)
    row.send_enabled = bool(data.get("sendEnabled", True))
    row.enabled = bool(data.get("useOwnMailbox"))
    row.smtp_host, row.smtp_port, row.security, row.smtp_user = host, int(data["smtpPort"]), data["security"], user
    row.from_name = (data.get("fromName") or "").strip()
    row.from_email = from_email
    row.reply_to = reply_to
    row.cc = _clean_emails(data.get("cc"), "Cc")
    row.bcc = _clean_emails(data.get("bcc"), "Bcc")
    pw = data.get("smtpPassword")
    if pw is not None:
        row.smtp_password_sealed = secret_box.seal(pw, settings.encryption_secret, _SECRET_PURPOSE) if pw != "" else None
    row.updated_by = actor_id
    session.flush()
    return row


def reset(tenant_id: uuid.UUID, key: str) -> None:
    """Back to the default: drops this kind's own mailbox, switches and recipients."""
    _require_key(key)
    row = get_row(tenant_id, key)
    if row is not None:
        session.delete(row)
        session.flush()


def copy_mailbox(tenant_id: uuid.UUID, key: str, source_key: str, *, actor_id) -> EmailConfig:
    """Copies another kind's mailbox (server, login - including the saved password - and sender) into this one, so the
    same account can serve several kinds without retyping its password. Cc/Bcc and the on/off switches stay as they are."""
    _require_key(key)
    _require_key(source_key)
    src = get_row(tenant_id, source_key)
    if src is None or not src.smtp_host or not src.from_email:
        raise rule_violation("That email type has no mailbox saved yet", code="EMAIL_CONFIG_INCOMPLETE")
    row = get_row(tenant_id, key)
    if row is None:
        row = EmailConfig(tenant_id=tenant_id, purpose_key=key, cc=[], bcc=[])
        session.add(row)
    row.smtp_host, row.smtp_port, row.security, row.smtp_user = src.smtp_host, src.smtp_port, src.security, src.smtp_user
    row.smtp_password_sealed = src.smtp_password_sealed
    row.from_name, row.from_email, row.reply_to = src.from_name, src.from_email, src.reply_to
    row.enabled = True
    row.updated_by = actor_id
    session.flush()
    return row


def _password(row: EmailConfig) -> str:
    if not row.smtp_password_sealed:
        return ""
    try:
        return secret_box.unseal(row.smtp_password_sealed, settings.encryption_secret, _SECRET_PURPOSE)
    except Exception:  # noqa: BLE001 - ENCRYPTION_SECRET was rotated; the password must be typed again
        return ""


def _settings_of(row: EmailConfig) -> MailSettings:
    return MailSettings(row.smtp_host, row.smtp_port, row.security, row.smtp_user, _password(row), _from_header(row), row.reply_to, source="tenant")


def resolve(tenant_id: uuid.UUID, template_key: str | None) -> MailSettings:
    """The mailbox a message of this kind leaves through."""
    row = get_row(tenant_id, template_key or "")
    if row is None or not row.enabled or not row.smtp_host or not row.from_email:
        return notification_transport.env_mail_settings()
    return _settings_of(row)


def purpose_rules(tenant_id: uuid.UUID, template_key: str) -> dict:
    """{enabled, cc, bcc} for one email kind: on, with no extra recipients, until someone says otherwise."""
    row = get_row(tenant_id, template_key)
    if row is None:
        return {"enabled": True, "cc": [], "bcc": []}
    return {"enabled": bool(row.send_enabled), "cc": list(row.cc or []), "bcc": list(row.bcc or [])}


def send_test(tenant_id: uuid.UUID, key: str, to: str) -> dict:
    """Sends through THIS kind's saved mailbox (switched on or not) and records the outcome on it."""
    _require_key(key)
    row = get_row(tenant_id, key)
    if row is None or not row.smtp_host or not row.from_email:
        raise rule_violation("Save the mail server and sender address first, then send a test", code="EMAIL_CONFIG_INCOMPLETE")
    if not _EMAIL_RE.match(to or ""):
        raise rule_violation(f'"{to}" is not a valid email address', code="RECIPIENT_INVALID")
    label = _require_key(key)["label"]
    result = notification_transport.send_email(
        to=[to], cc=[], bcc=[], subject=f"Test email from Simple ERP - {label}",
        text=f"This is a test message for the \"{label}\" emails. If you can read it, the mailbox saved for them in Email Config works.",
        html=f"<p>This is a test message for the <b>{label}</b> emails.</p><p>If you can read it, the mailbox saved for them in <b>Email Config</b> works.</p>",
        mail=_settings_of(row),
    )
    row.last_test_at = datetime.now(timezone.utc)
    row.last_test_ok = bool(result["ok"])
    row.last_test_error = None if result["ok"] else (result.get("error") or "Unknown error")[:500]
    session.flush()
    return {"ok": row.last_test_ok, "error": row.last_test_error}
