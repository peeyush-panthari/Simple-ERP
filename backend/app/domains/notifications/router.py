"""GET/POST /notifications, GET /delivery-logs, POST /notifications/{id}/retry,
GET/PUT /templates, POST /templates/{key}/preview, GET /suppressions,
DELETE /suppressions/{address}, POST /internal/delivery-events. Ported 1:1
(behavior) from backend_py/app/routes/notifications.py.

POST /notifications/send and POST /internal/delivery-events deliberately get
NO permission dependency (only authentication) - matching the original's
real, documented gap where these are the single entry point every other
module uses. Every other route gets a real notification:read/send gate.
"""

from __future__ import annotations

import uuid as uuid_mod

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, Field

from app.core.auth import Actor, CurrentActor, require_permission
from app.core.db import session
from app.core.errors import bad_request
from app.core.pagination import ListQuery, list_response, offset_of
from app.models.delivery_log import DeliveryLog
from app.models.notification import Notification
from app.services import notification_repo

router = APIRouter(prefix="/api/v1", tags=["notifications"])


class SendBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    template: str
    channel: str = "email"
    to: list[str] = Field(min_length=1)
    cc: list[str] = Field(default_factory=list)
    bcc: list[str] = Field(default_factory=list)
    data: dict = Field(default_factory=dict)
    attachments: list[dict] = Field(default_factory=list)
    relatedType: str | None = None
    relatedId: str | None = None
    deferred: bool = False


class TemplateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    channel: str = "email"
    subject: str | None = None
    bodyText: str
    bodyHtml: str | None = None
    description: str | None = None


class PreviewBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    channel: str = "email"
    data: dict = Field(default_factory=dict)


class DeliveryEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    messageId: str | None = None
    address: str
    outcome: str
    detail: str | None = None


class DeliveryEventsBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str
    events: list[DeliveryEvent] = Field(min_length=1)


def _template_to_api(row) -> dict:
    return {
        "key": row.key,
        "channel": row.channel,
        "version": row.version,
        "subject": row.subject,
        "bodyText": row.body_text,
        "bodyHtml": row.body_html,
        "description": row.description,
        "active": row.active,
        "isBuiltin": row.is_builtin,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }


def _suppression_to_api(row) -> dict:
    return {
        "address": row.address,
        "reason": row.reason,
        "source": row.source,
        "suppressedAt": row.suppressed_at.isoformat() if row.suppressed_at else None,
    }


def _delivery_log_to_api(row: DeliveryLog) -> dict:
    return {
        "id": str(row.id),
        "notificationId": str(row.notification_id),
        "attempt": row.attempt,
        "outcome": row.outcome,
        "provider": row.provider,
        "providerMessageId": row.provider_message_id,
        "detail": row.detail,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }


@router.get("/notifications")
def list_notifications(
    actor: Actor = Depends(require_permission("notification:read")),
    query: ListQuery = Depends(),
    relatedType: str | None = None,
    relatedId: str | None = None,
    status: str | None = None,
):
    q = Notification.query.filter(Notification.tenant_id == actor["tenant_id"])
    if relatedType:
        q = q.filter(Notification.related_type == relatedType)
    if relatedId:
        q = q.filter(Notification.related_id == relatedId)
    if status:
        q = q.filter(Notification.status == status)

    total = q.count()
    rows = q.order_by(Notification.created_at.desc()).limit(query.limit).offset(offset_of(query)).all()
    return list_response([notification_repo.to_api(r) for r in rows], query, total)


@router.post("/notifications/send", status_code=201)
def send_notification_route(body: SendBody, actor: CurrentActor):
    """Deliberately no permission dependency - matches the original's real
    gap (any authenticated user can send any templated notification)."""
    result = notification_repo.send_notification(
        actor["tenant_id"],
        template=body.template,
        channel=body.channel,
        to=body.to,
        cc=body.cc,
        bcc=body.bcc,
        data=body.data,
        attachments=body.attachments,
        related_type=body.relatedType,
        related_id=body.relatedId,
        deferred=body.deferred,
    )
    session.commit()
    return result


@router.get("/delivery-logs")
def list_delivery_logs(actor: Actor = Depends(require_permission("notification:read")), query: ListQuery = Depends(), notificationId: uuid_mod.UUID | None = None):
    q = DeliveryLog.query.filter(DeliveryLog.tenant_id == actor["tenant_id"])
    if notificationId:
        q = q.filter(DeliveryLog.notification_id == notificationId)

    total = q.count()
    rows = q.order_by(DeliveryLog.created_at.desc()).limit(query.limit).offset(offset_of(query)).all()
    return list_response([_delivery_log_to_api(r) for r in rows], query, total)


@router.post("/notifications/{id}/retry")
def retry_notification_route(id: uuid_mod.UUID, actor: Actor = Depends(require_permission("notification:send"))):
    return notification_repo.retry_notification(actor["tenant_id"], id)


@router.get("/templates")
def list_templates_route(actor: Actor = Depends(require_permission("notification:read"))):
    rows = notification_repo.list_latest_templates(actor["tenant_id"])
    return {"data": [_template_to_api(r) for r in rows]}


@router.get("/templates/{key}")
def get_template_versions_route(key: str, actor: Actor = Depends(require_permission("notification:read"))):
    rows = notification_repo.list_template_versions(actor["tenant_id"], key)
    return {"data": [_template_to_api(r) for r in rows]}


@router.put("/templates/{key}")
def update_template_route(key: str, body: TemplateBody, actor: Actor = Depends(require_permission("notification:send"))):
    row = notification_repo.update_template(
        actor["tenant_id"],
        key,
        channel=body.channel,
        subject=body.subject,
        body_text=body.bodyText,
        body_html=body.bodyHtml,
        description=body.description,
        actor_id=actor["user_id"],
        actor_email=actor.get("email"),
    )
    session.commit()
    return _template_to_api(row)


@router.post("/templates/{key}/preview")
def preview_template_route(key: str, body: PreviewBody, actor: Actor = Depends(require_permission("notification:read"))):
    return notification_repo.preview_template(actor["tenant_id"], key, body.channel, body.data)


@router.get("/suppressions")
def list_suppressions_route(actor: Actor = Depends(require_permission("notification:read"))):
    rows = notification_repo.list_suppressions(actor["tenant_id"])
    return {"data": [_suppression_to_api(r) for r in rows]}


@router.delete("/suppressions/{address}", status_code=204)
def remove_suppression_route(address: str, actor: Actor = Depends(require_permission("notification:send"))):
    notification_repo.remove_suppression(actor["tenant_id"], address, actor_id=actor["user_id"], actor_email=actor.get("email"))
    session.commit()
    return Response(status_code=204)


@router.post("/internal/delivery-events")
def delivery_events_route(body: DeliveryEventsBody, actor: CurrentActor):
    """Deliberately no permission dependency - matches the original's real
    gap on this internal webhook endpoint."""
    if not body.events:
        raise bad_request("events must not be empty")
    return notification_repo.process_delivery_events(actor["tenant_id"], body.provider, [e.model_dump() for e in body.events])
