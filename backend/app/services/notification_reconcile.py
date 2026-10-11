"""When delivery happens later, in the worker, the document that asked for the
email (invoice, PO, RFQ invitation, dispatch) was left saying "queued" - this
writes the outcome back onto it once the notification reaches a terminal
state. In inline mode the request itself sets that state from the send
result, so this only runs from the worker."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.models.dispatch import Dispatch
from app.models.invoice import Invoice
from app.models.notification import Notification
from app.models.purchase_order import PurchaseOrder
from app.models.rfq_invitation import RfqInvitation

_TERMINAL = ("sent", "failed", "bounced")


def reconcile_related(note: Notification) -> None:
    """Idempotent; a no-op for a notification still retrying (`queued`)."""
    if note.status not in _TERMINAL or not note.related_type or not note.related_id:
        return
    ok = note.status == "sent"
    try:
        related_id = uuid.UUID(note.related_id)
    except ValueError:
        return

    if note.related_type == "invoice":
        row = Invoice.query.filter_by(tenant_id=note.tenant_id, id=related_id).first()
        if row:
            row.email_state = "sent" if ok else "failed"
            row.email_error = None if ok else note.last_error
    elif note.related_type == "purchase-order":
        row = PurchaseOrder.query.filter_by(tenant_id=note.tenant_id, id=related_id).first()
        if row:
            row.email_state = "sent" if ok else "failed"
            row.email_error = None if ok else note.last_error
            if ok:
                row.email_sent_at = datetime.now(timezone.utc)
    elif note.related_type == "rfq":
        for invitation in RfqInvitation.query.filter(RfqInvitation.rfq_id == related_id, RfqInvitation.carrier_email.in_(note.recipients)).all():
            invitation.email_state = "sent" if ok else "failed"
            invitation.email_error = None if ok else note.last_error
    elif note.related_type == "dispatch":
        row = Dispatch.query.filter_by(tenant_id=note.tenant_id, id=related_id).first()
        if row:
            row.warehouse_notify_state = "sent" if ok else "failed"
