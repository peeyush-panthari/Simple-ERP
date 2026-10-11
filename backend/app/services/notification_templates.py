"""The 5 built-in notification templates + seed_templates()'s exact
hash-based upsert logic - ported 1:1 (behavior) from domain/templates.ts +
the boot-time seeding in index.ts.

Templates are stored as PLAIN TEXT containing {{...}} tokens - rendered
later at send time through notification_render.py, not pre-rendered here.

seed_templates() runs on every app boot (see app/__init__.py::create_app()),
matching Node's real onBoot lifecycle - NOT a one-off bootstrap command.
Only ever touches version=1 rows for the single default tenant - a latent
single-tenant assumption in Node itself, not something to generalize.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid

from app.core.config import settings
from app.core.db import session
from app.models.notification_template import NotificationTemplate

logger = logging.getLogger("axon.notification.templates")

_DEFAULT_FOOTER = "This is an automated message from Axon ERP. Please do not reply to this address."


def _layout(title: str, body: str, footer: str = _DEFAULT_FOOTER) -> str:
    return f"""<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:24px 0;">
  <tr><td align="center">
    <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:8px;overflow:hidden;font-family:Helvetica,Arial,sans-serif;">
      <tr><td style="background:#0f172a;color:#ffffff;padding:20px 28px;font-size:16px;font-weight:700;">{title}</td></tr>
      <tr><td style="padding:28px;font-size:14px;color:#0f172a;line-height:1.6;">{body}</td></tr>
      <tr><td style="background:#f8fafc;padding:16px 28px;font-size:11px;color:#64748b;">{footer}</td></tr>
    </table>
  </td></tr>
</table>"""


_LINE_TABLE_FRAGMENT = """<table width="100%" cellpadding="6" style="border-collapse:collapse;margin:12px 0;">
  <tr style="background:#f1f5f9;font-size:11px;text-transform:uppercase;color:#475569;"><td>SKU</td><td>Description</td><td>Qty</td><td>UOM</td><td>Unit price</td><td>Amount</td></tr>
  {{#each lines}}<tr style="border-bottom:1px solid #e2e8f0;"><td>{{sku}}</td><td>{{description}}</td><td>{{quantity}}</td><td>{{uom}}</td><td>{{unitPrice}}</td><td>{{grossAmount}}</td></tr>{{/each}}
</table>"""

_PDF_LINK_FRAGMENT = '{{#if pdfUrl}}<p><a href="{{pdfUrl}}">Download PDF</a></p>{{/if}}'


class SeedTemplate:
    def __init__(self, key: str, channel: str, subject: str | None, body_text: str, body_html: str | None, description: str):
        self.key = key
        self.channel = channel
        self.subject = subject
        self.body_text = body_text
        self.body_html = body_html
        self.description = description


SEED_TEMPLATES: list[SeedTemplate] = [
    SeedTemplate(
        "purchase-order.issued",
        "email",
        "Purchase order {{number}} from Axon Industries",
        "Purchase order {{number}} has been issued to {{vendor.name}}.\nDated {{poDate}}, required by {{expectedDate}}.\nDeliver to: {{warehouse}}.\nTotal: {{currency}} {{total}} ({{paymentTerms}}).",
        _layout(
            "Purchase order {{number}}",
            f'<p>Purchase order <b>{{{{number}}}}</b> has been issued to <b>{{{{vendor.name}}}}</b>.</p><p>Dated {{{{poDate}}}}, required by {{{{expectedDate}}}}. Deliver to: {{{{warehouse}}}}.</p>{_LINE_TABLE_FRAGMENT}<p>Total: {{{{currency}}}} {{{{total}}}} ({{{{paymentTerms}}}})</p>{_PDF_LINK_FRAGMENT}',
        ),
        "Sent to a vendor when a purchase order is issued.",
    ),
    SeedTemplate(
        "invoice.issued",
        "email",
        "Invoice {{number}} — {{currency}} {{total}} due {{dueDate}}",
        "Invoice {{number}} for {{currency}} {{total}} is due on {{dueDate}}.",
        _layout("Invoice {{number}}", f'<p>Invoice <b>{{{{number}}}}</b> for {{{{currency}}}} {{{{total}}}} is due on {{{{dueDate}}}}.</p>{_PDF_LINK_FRAGMENT}'),
        "Sent to a customer when a sales invoice is generated.",
    ),
    SeedTemplate(
        "purchase-rfq.issued",
        "email",
        "Request for quotation {{rfqNumber}} - please quote by {{dueDate}}",
        "Dear {{vendorName}}, we would like a quotation for the items below (request {{rfqNumber}}). Please reply by {{dueDate}} with your unit price, GST, lead time and payment terms. Deliver to: {{warehouse}}. Required by: {{requiredBy}}. {{terms}}",
        _layout(
            "Request for quotation {{rfqNumber}}",
            "<p>Dear {{vendorName}},</p><p>We would like a quotation for the items below. Please reply by <b>{{dueDate}}</b> with your unit price, GST, lead time and payment terms.</p>"
            "<table width=\"100%\" cellpadding=\"6\" style=\"border-collapse:collapse;margin:12px 0;\"><tr style=\"background:#f1f5f9;font-size:11px;text-transform:uppercase;color:#475569;\"><td>Item</td><td>Quantity</td><td>Notes</td></tr>"
            "{{#each lines}}<tr style=\"border-bottom:1px solid #e2e8f0;\"><td>{{itemName}}</td><td>{{quantity}} {{uom}}</td><td>{{notes}}</td></tr>{{/each}}</table>"
            "<p>Deliver to: {{warehouse}}. Required by: {{requiredBy}}.</p><p>{{terms}}</p><p>Regards,<br>{{buyerName}}</p>",
        ),
        "Sent to a vendor when Purchase asks for a quotation on an approved requisition.",
    ),
    SeedTemplate(
        "logistics.rfq",
        "email",
        "RFQ {{rfqNumber}} — {{lane}} (respond by {{dueAt}})",
        "You have been invited to quote on {{rfqNumber}} for the lane {{lane}}. Pickup address: {{pickupAddress}}. Target date: {{targetDate}}. Service level: {{serviceLevel}}. Weight: {{weightKg}} kg. Please respond by {{dueAt}}.",
        _layout(
            "RFQ {{rfqNumber}}",
            "<p>You have been invited to quote on <b>{{rfqNumber}}</b> for the lane {{lane}}.</p><p>Pickup address: {{pickupAddress}}.</p><p>Target date: {{targetDate}}. Service level: {{serviceLevel}}. Weight: {{weightKg}} kg.</p><p>Please respond by {{dueAt}}.</p>",
        ),
        "Sent to a carrier when a transport request goes out for quotation.",
    ),
    SeedTemplate(
        "logistics.pre-dispatch",
        "email",
        "Dispatch {{dispatchNumber}} — prepare goods for collection",
        "Dispatch {{dispatchNumber}} (against request {{requestNumber}}) has been booked with {{carrier}}. Vehicle: {{vehicleNumber}}. ETA: {{eta}}. Please have the goods ready for collection.",
        _layout("Dispatch {{dispatchNumber}}", "<p>Dispatch <b>{{dispatchNumber}}</b> (against request {{requestNumber}}) has been booked with {{carrier}}.</p><p>Vehicle: {{vehicleNumber}}. ETA: {{eta}}.</p><p>Please have the goods ready for collection.</p>"),
        "Sent to the source warehouse ahead of a scheduled carrier collection.",
    ),
    SeedTemplate(
        "user.invitation",
        "email",
        "You have been invited to Axon ERP",
        "Hello {{displayName}}, you have been invited to Axon ERP. Use this token to set your password: {{inviteToken}}",
        _layout("You have been invited to Axon ERP", "<p>Hello {{displayName}}, you have been invited to Axon ERP.</p><p>Use this token to set your password: <b>{{inviteToken}}</b></p>"),
        "Sent when a new user is created without a password (invite flow).",
    ),
    SeedTemplate(
        "user.password_reset",
        "email",
        "Reset your Axon ERP password",
        "Hello {{displayName}}, a password reset request was received for your account. Use this reset token: {{resetToken}} (valid for 1 hour). If you did not request this, you can ignore this email.",
        _layout("Reset your password", "<p>Hello {{displayName}},</p><p>A password reset request was received for your account.</p><p>Use this reset token to change your password: <b>{{resetToken}}</b></p><p>This token is valid for 1 hour. If you did not request a password reset, you can safely ignore this email.</p>"),
        "Sent when a user requests a password reset.",
    ),
]


def _hash_of(t) -> str:
    payload = json.dumps([t.subject or "", t.body_text, t.body_html or "", t.description])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _is_unedited(row: NotificationTemplate) -> bool:
    """Recomputes the hash of the row's CURRENT stored content and compares
    to its own recorded builtin_hash - a defensive double-check, not an
    independent signal in practice (seed_templates is the only writer of
    builtin_hash), preserved exactly as Node has it."""
    current_hash = _hash_of(SeedTemplate(row.key, row.channel, row.subject, row.body_text, row.body_html, row.description or ""))
    return current_hash == row.builtin_hash


def seed_templates() -> None:
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    tenant_id = uuid.UUID(settings.default_tenant_id)
    for t in SEED_TEMPLATES:
        builtin_hash = _hash_of(t)
        row = NotificationTemplate.query.filter_by(tenant_id=tenant_id, key=t.key, channel=t.channel, version=1).first()
        if row is None:
            stmt = (
                pg_insert(NotificationTemplate)
                .values(tenant_id=tenant_id, key=t.key, channel=t.channel, version=1, subject=t.subject, body_text=t.body_text, body_html=t.body_html, description=t.description, active=True, is_builtin=True, builtin_hash=builtin_hash)
                .on_conflict_do_nothing(index_elements=["tenant_id", "key", "channel", "version"])
            )
            session.execute(stmt)
            continue

        if row.builtin_hash == builtin_hash:
            continue  # already current

        untouched = row.is_builtin and (row.builtin_hash is None or _is_unedited(row))
        if untouched:
            row.subject = t.subject
            row.body_text = t.body_text
            row.body_html = t.body_html
            row.description = t.description
            row.builtin_hash = builtin_hash
        # else: tenant has edited it - preserve, skip silently

    session.commit()
