"""Notification send/deliver/retry + template CRUD + suppression list - the
plain, unguarded send_notification()/deliver_now() functions other already-
built modules call directly, plus the projections routes/notifications.py
wraps (some with real permission checks, two deliberately without - see
plan's design section for POST /notifications/send and
POST /internal/delivery-events).

No automatic background delivery-retry poller (see plan) - send_notification()
always delivers inline, matching every real Node call site (none of which
ever passes deferred=true); /notifications/:id/retry also delivers inline
on demand, matching Node's own retry route exactly.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import and_, func

from app.core.config import settings
from app.core.errors import conflict, not_found, rule_violation
from app.core.db import session
from app.models.delivery_log import DeliveryLog
from app.models.notification import Notification
from app.models.notification_template import NotificationTemplate
from app.models.suppression import Suppression
from app.core import messaging
from app.services import email_config_repo, notification_render, notification_transport
from app.core.audit import audit

# ---- notifications ----------------------------------------------------


def find_notification(tenant_id: uuid.UUID, id: uuid.UUID) -> Notification | None:
    return Notification.query.filter_by(tenant_id=tenant_id, id=id).first()


def require_notification(tenant_id: uuid.UUID, id: uuid.UUID) -> Notification:
    row = find_notification(tenant_id, id)
    if not row:
        raise not_found(f"Notification {id}")
    return row


def to_api(row: Notification) -> dict:
    return {
        "id": str(row.id),
        "templateKey": row.template_key,
        "channel": row.channel,
        "recipients": row.recipients,
        "cc": row.cc,
        "bcc": row.bcc,
        "subject": row.subject,
        "status": row.status,
        "attempts": row.attempts,
        "lastError": row.last_error,
        "provider": row.provider,
        "relatedType": row.related_type,
        "relatedId": row.related_id,
        "sentAt": row.sent_at.isoformat() if row.sent_at else None,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }


def send_notification(
    tenant_id: uuid.UUID,
    *,
    template: str,
    channel: str = "email",
    to: list[str],
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    data: dict | None = None,
    attachments: list[dict] | None = None,
    related_type: str | None = None,
    related_id: str | None = None,
    deferred: bool = False,
) -> dict:
    """Direct-call equivalent of POST /notifications/send. Every recipient's
    header-injection-checked; email recipients are additionally shape-
    checked. Suppression is checked only against `to`, never cc/bcc -
    matching Node exactly."""
    cc = cc or []
    bcc = bcc or []
    data = data or {}
    attachments = attachments or []

    tpl = (
        NotificationTemplate.query.filter_by(tenant_id=tenant_id, key=template, channel=channel, active=True)
        .order_by(NotificationTemplate.version.desc())
        .first()
    )
    if not tpl:
        raise not_found(f"Template {template} ({channel})")

    if channel == "email":
        # Foundation > Email Config: a kind of email can be switched off, and can carry standing Cc/Bcc recipients.
        rules = email_config_repo.purpose_rules(tenant_id, template)
        if not rules["enabled"]:
            raise rule_violation("This kind of email is switched off in Foundation > Email Config", code="EMAIL_PURPOSE_DISABLED")
        have = {a.lower() for a in [*to, *cc, *bcc]}
        cc = [*cc, *[a for a in rules["cc"] if a.lower() not in have]]
        have |= {a.lower() for a in cc}
        bcc = [*bcc, *[a for a in rules["bcc"] if a.lower() not in have]]

    recipients = [notification_render.assert_no_header_injection("recipient", r) for r in to]
    if channel == "email":
        invalid = [r for r in recipients if not notification_render.is_plausible_email(r)]
        if invalid:
            raise rule_violation(f"These recipients are not valid email addresses: {', '.join(invalid)}", code="RECIPIENT_INVALID")

    suppressed_addrs = {
        s.address for s in Suppression.query.filter(Suppression.tenant_id == tenant_id, Suppression.address.in_([r.lower() for r in recipients])).all()
    }
    deliverable = [r for r in recipients if r.lower() not in suppressed_addrs]
    suppressed = [r for r in recipients if r.lower() in suppressed_addrs]

    if not deliverable:
        raise conflict(f"Every recipient is suppressed ({', '.join(recipients)})", code="ALL_RECIPIENTS_SUPPRESSED")

    rendered = notification_render.render(subject=tpl.subject, body_text=tpl.body_text, body_html=tpl.body_html, data=data)

    row = Notification(
        tenant_id=tenant_id,
        template_key=template,
        template_version=tpl.version,
        channel=channel,
        recipients=deliverable,
        cc=cc,
        bcc=bcc,
        subject=rendered["subject"],
        body_text=rendered["text"],
        body_html=rendered["html"],
        data=data,
        attachments=attachments,
        related_type=related_type,
        related_id=related_id,
        status="queued",
    )
    session.add(row)
    session.flush()

    result = {"id": str(row.id), "status": row.status, "recipients": deliverable, "suppressed": suppressed}
    if settings.async_notifications:
        # Delivery is the worker's job: hand it the row once this
        # transaction commits (see core/messaging.py).
        messaging.publish_after_commit(settings.notification_queue, {"tenantId": str(tenant_id), "notificationId": str(row.id)})
        return result
    if deferred:
        return result

    delivery = deliver_now(tenant_id, row.id)
    result["status"] = delivery["status"]
    if delivery.get("error"):
        result["error"] = delivery["error"]
    return result


def delivery_state(result: dict, *, queued_state: str = "queued") -> str:
    """Maps send_notification()'s result onto the owning document's
    email_state: "sent" and "failed" as before, plus the new "queued" for a
    notification handed to the worker (`queued_state` lets a column whose
    CHECK constraint has no 'queued' value say "not_sent" instead)."""
    if result["status"] == "sent":
        return "sent"
    if result["status"] == "queued" and settings.async_notifications:
        return queued_state
    return "failed"


def deliver_now(tenant_id: uuid.UUID, notification_id: uuid.UUID) -> dict:
    row = (
        session.query(Notification)
        .filter(Notification.tenant_id == tenant_id, Notification.id == notification_id, Notification.status.in_(("queued", "sending", "failed")))
        .with_for_update()
        .first()
    )
    if not row:
        return {"status": "queued"}  # nothing to do - already sent, or not found

    row.status = "sending"
    row.attempts += 1

    if row.channel == "email":
        result = notification_transport.send_email(
            to=row.recipients, cc=row.cc, bcc=row.bcc, subject=row.subject or "", text=row.body_text, html=row.body_html,
            mail=email_config_repo.resolve(tenant_id, row.template_key),
        )
    elif row.channel == "sms":
        result = notification_transport.send_sms(to=row.recipients[0] if row.recipients else "", body=row.body_text)
    else:
        result = notification_transport.send_push(to=row.recipients[0] if row.recipients else "", body=row.body_text)

    exhausted = row.attempts >= settings.max_delivery_attempts
    give_up = bool(result.get("permanent")) or exhausted

    session.add(DeliveryLog(tenant_id=tenant_id, notification_id=row.id, attempt=row.attempts, outcome="sent" if result["ok"] else "failed", provider=result.get("provider"), detail=result.get("error")))

    if result["ok"]:
        row.status = "sent"
        row.sent_at = datetime.now(timezone.utc)
        row.provider = result.get("provider")
        row.last_error = None
    else:
        row.status = "failed" if give_up else "queued"
        row.last_error = result.get("error")
        row.provider = result.get("provider")
        row.next_attempt_at = datetime.now(timezone.utc) if give_up else _next_attempt_at(row.attempts)

    session.flush()

    return {"status": row.status, "error": row.last_error}


def _next_attempt_at(attempts: int) -> datetime:
    from datetime import timedelta

    delay = notification_render.next_attempt_delay_seconds(attempts, settings.retry_base_seconds)
    return datetime.now(timezone.utc) + timedelta(seconds=delay)


def retry_notification(tenant_id: uuid.UUID, id: uuid.UUID) -> dict:
    row = require_notification(tenant_id, id)
    if row.status == "sent":
        raise conflict(f"Notification {id} has already been sent", code="ALREADY_SENT")
    row.status = "queued"
    row.next_attempt_at = datetime.now(timezone.utc)
    row.attempts = 0
    row.last_error = None
    session.flush()
    return deliver_now(tenant_id, id)


# ---- templates ----------------------------------------------------------


def list_latest_templates(tenant_id: uuid.UUID) -> list[NotificationTemplate]:
    """distinct on (key, channel), latest version regardless of active flag."""
    from sqlalchemy import func as sa_func

    subq = (
        session.query(NotificationTemplate.key, NotificationTemplate.channel, sa_func.max(NotificationTemplate.version).label("max_version"))
        .filter(NotificationTemplate.tenant_id == tenant_id)
        .group_by(NotificationTemplate.key, NotificationTemplate.channel)
        .subquery()
    )
    return (
        session.query(NotificationTemplate)
        .join(subq, and_(NotificationTemplate.key == subq.c.key, NotificationTemplate.channel == subq.c.channel, NotificationTemplate.version == subq.c.max_version))
        .filter(NotificationTemplate.tenant_id == tenant_id)
        .order_by(NotificationTemplate.key, NotificationTemplate.channel)
        .all()
    )


def list_template_versions(tenant_id: uuid.UUID, key: str) -> list[NotificationTemplate]:
    return NotificationTemplate.query.filter_by(tenant_id=tenant_id, key=key).order_by(NotificationTemplate.version.desc()).all()


def update_template(tenant_id: uuid.UUID, key: str, *, channel: str, subject: str | None, body_text: str, body_html: str | None, description: str | None, actor_id, actor_email: str | None) -> NotificationTemplate:
    max_version = session.query(func.max(NotificationTemplate.version)).filter_by(tenant_id=tenant_id, key=key, channel=channel).scalar() or 0
    NotificationTemplate.query.filter_by(tenant_id=tenant_id, key=key, channel=channel).update({"active": False})
    row = NotificationTemplate(tenant_id=tenant_id, key=key, channel=channel, version=max_version + 1, subject=subject, body_text=body_text, body_html=body_html, description=description, active=True, is_builtin=False)
    session.add(row)
    session.flush()
    audit(tenant_id=tenant_id, actor_id=actor_id, actor_email=actor_email, action="notification.template.updated", entity_type="notification-template", entity_id=key, meta={"channel": channel, "version": row.version})
    return row


def preview_template(tenant_id: uuid.UUID, key: str, channel: str, data: dict) -> dict:
    tpl = NotificationTemplate.query.filter_by(tenant_id=tenant_id, key=key, channel=channel, active=True).order_by(NotificationTemplate.version.desc()).first()
    if not tpl:
        raise not_found(f"Template {key} ({channel})")
    return notification_render.render(subject=tpl.subject, body_text=tpl.body_text, body_html=tpl.body_html, data=data)


# ---- suppressions ---------------------------------------------------------


def list_suppressions(tenant_id: uuid.UUID) -> list[Suppression]:
    return Suppression.query.filter_by(tenant_id=tenant_id).order_by(Suppression.suppressed_at.desc()).limit(500).all()


def remove_suppression(tenant_id: uuid.UUID, address: str, *, actor_id, actor_email: str | None) -> None:
    row = Suppression.query.filter_by(tenant_id=tenant_id, address=address.lower()).first()
    if row:
        session.delete(row)
        audit(tenant_id=tenant_id, actor_id=actor_id, actor_email=actor_email, action="notification.suppression.removed", entity_type="suppression", entity_id=address.lower())


# ---- delivery-events webhook (POST /internal/delivery-events) -------------


def process_delivery_events(tenant_id: uuid.UUID, provider: str, events: list[dict]) -> dict:
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    # Batch-fetch every notification the events could reference up front,
    # instead of one query per event (providers deliver these in batches).
    message_ids = {event.get("messageId") or "" for event in events}  # matches Node's `?? ""` exactly - never matches a real row
    notifications_by_message_id = {
        n.provider_message_id: n
        for n in Notification.query.filter(Notification.tenant_id == tenant_id, Notification.provider_message_id.in_(message_ids)).all()
    }

    suppressed_count = 0
    for event in events:
        message_id = event.get("messageId") or ""  # matches Node's `?? ""` exactly - never matches a real row
        notification = notifications_by_message_id.get(message_id)
        if notification:
            session.add(DeliveryLog(tenant_id=tenant_id, notification_id=notification.id, attempt=notification.attempts, outcome=event["outcome"], provider=provider, provider_message_id=event.get("messageId"), detail=event.get("detail")))
            if event["outcome"] == "bounced":
                notification.status = "bounced"

        if event["outcome"] in ("bounced", "complained"):
            stmt = (
                pg_insert(Suppression)
                .values(tenant_id=tenant_id, address=event["address"].lower(), reason=event["outcome"], source=provider)
                .on_conflict_do_update(index_elements=["tenant_id", "address"], set_={"reason": event["outcome"], "suppressed_at": datetime.now(timezone.utc)})
            )
            session.execute(stmt)
            suppressed_count += 1

    session.commit()
    return {"processed": len(events), "suppressed": suppressed_count}
