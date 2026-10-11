"""Procurement > Sourcing: request for quotation, quotation evaluation and comparison, award, purchase orders.

GET    /api/v1/purchase-rfqs                          list
POST   /api/v1/purchase-rfqs                          start sourcing for an approved requisition and invite vendors
GET    /api/v1/purchase-rfqs/{id}                     header, items, invited vendors and the quotations recorded so far
GET    /api/v1/purchase-rfqs/{id}/comparison          every offer side by side, per item and per vendor (tax and freight in)
POST   /api/v1/purchase-rfqs/{id}/vendors             invite more vendors
DELETE /api/v1/purchase-rfqs/{id}/vendors/{vendorId}  withdraw an invitation (only before they have quoted)
POST   /api/v1/purchase-rfqs/{id}/vendors/{vendorId}/resend    send the request email again
POST   /api/v1/purchase-rfqs/{id}/vendors/{vendorId}/decline   record that the vendor is not quoting
PUT    /api/v1/purchase-rfqs/{id}/quotations/{vendorId}        record (or replace) what a vendor offered
POST   /api/v1/purchase-rfqs/{id}/award               pick the winning vendor per item
POST   /api/v1/purchase-rfqs/{id}/reopen              undo the award (before any purchase order exists)
POST   /api/v1/purchase-rfqs/{id}/purchase-orders     raise one purchase order per winning vendor
POST   /api/v1/purchase-rfqs/{id}/cancel              drop the RFQ; the requisition goes back to "approved"

Permissions: sourcing:read to look, sourcing:write to run the RFQ, sourcing:award (+ po:write) to award and order.
"""

from __future__ import annotations

import uuid as uuid_mod
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_

from app.core.audit import audit
from app.core.auth import Actor, require_permission
from app.core.access_scope import assert_warehouse_in_scope
from app.core.db import session
from app.core.errors import ProblemError, rule_violation
from app.core.money import decimal_str, to_decimal
from app.core.pagination import ListQuery, list_response, offset_of
from app.core.scalars import DecimalString
from app.domains.procurement.router import _create_po_postgres
from app.domains.procurement.schemas import LineBody, PoBody
from app.models.purchase_requisition import PurchaseRequisition
from app.models.purchase_rfq import PurchaseQuotation, PurchaseQuotationLine, PurchaseRfq, PurchaseRfqLine, PurchaseRfqVendor
from app.services import notification_repo, party_summary, requisition_repo, sourcing_repo, warehouse_repo
from app.services.sequences import next_document_number
from app.services.tax_codes import is_known_tax_code

router = APIRouter(prefix="/api/v1/purchase-rfqs", tags=["sourcing"])

_TEMPLATE = "purchase-rfq.issued"


# ---- request bodies --------------------------------------------------------------------------------------------------


class CreateRfqBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requisitionId: uuid_mod.UUID
    vendorIds: list[uuid_mod.UUID] = Field(min_length=1, max_length=30)
    dueDate: date | None = None
    requiredBy: date | None = None
    warehouseId: uuid_mod.UUID | None = None
    terms: str | None = Field(default=None, max_length=1000)
    notes: str | None = Field(default=None, max_length=2000)
    send: bool = True


class InviteBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    vendorIds: list[uuid_mod.UUID] = Field(min_length=1, max_length=30)
    send: bool = True


class QuotationLineBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rfqLineId: uuid_mod.UUID
    unitPrice: DecimalString | None = None
    taxCode: str = Field(default="GST0", max_length=20)
    leadTimeDays: int | None = Field(default=None, ge=0, le=730)
    notes: str | None = Field(default=None, max_length=500)


class QuotationBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    quoteRef: str | None = Field(default=None, max_length=80)
    quoteDate: date | None = None
    validUntil: date | None = None
    paymentTerms: str | None = Field(default=None, max_length=120)
    deliveryDays: int | None = Field(default=None, ge=0, le=730)
    charges: DecimalString = "0"
    notes: str | None = Field(default=None, max_length=1000)
    lines: list[QuotationLineBody] = Field(min_length=1, max_length=200)


class AwardLineBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rfqLineId: uuid_mod.UUID
    vendorId: uuid_mod.UUID
    reason: str | None = Field(default=None, max_length=500)


class AwardBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    awards: list[AwardLineBody] = Field(min_length=1, max_length=200)


class CreatePosBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    warehouseId: uuid_mod.UUID | None = None
    expectedDate: date | None = None


class CancelBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=3, max_length=1000)


# ---- helpers ---------------------------------------------------------------------------------------------------------


def _actor_name(actor: Actor) -> str:
    return actor.get("name") or actor.get("email") or "Unknown user"


def _clean(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def _audit(actor: Actor, action: str, rfq: PurchaseRfq, reason: str | None = None, **meta) -> None:
    audit(tenant_id=actor["tenant_id"], actor_id=actor["user_id"], actor_email=actor["email"], action=action, entity_type="purchase-rfq", entity_id=str(rfq.id), reason=reason, meta={"number": rfq.number, "status": rfq.status, **meta})


def _detail(rfq: PurchaseRfq) -> dict:
    vendors = sourcing_repo.vendors_of(rfq.id)
    return sourcing_repo.to_api(rfq, lines=sourcing_repo.lines_of(rfq.id), vendors=vendors, quotes=sourcing_repo.quotations_of(rfq.id))


def _require_open(rfq: PurchaseRfq, doing: str) -> None:
    if rfq.status != "open":
        way = {"awarded": "reopen it first (Compare & award > Reopen)", "ordered": "purchase orders already exist for it", "cancelled": "start a new RFQ from the requisition"}.get(rfq.status, "check its status")
        raise rule_violation(f"{rfq.number} is {rfq.status}, so you cannot {doing}: {way}", code="RFQ_INVALID_STATE")


def _vendor_row(rfq: PurchaseRfq, vendor_id) -> PurchaseRfqVendor:
    row = PurchaseRfqVendor.query.filter_by(rfq_id=rfq.id, vendor_id=vendor_id).first()
    if not row:
        raise rule_violation(f"That vendor was not invited to {rfq.number}", code="RFQ_VENDOR_NOT_INVITED")
    return row


def _resolve_vendors(tenant_id, vendor_ids: list[uuid_mod.UUID]) -> list[dict]:
    errors, found, seen = [], [], set()
    for vid in vendor_ids:
        if vid in seen:
            continue
        seen.add(vid)
        try:
            v = party_summary.build_summary_by_id(tenant_id, vid)
        except ProblemError:
            errors.append({"field": "vendorIds", "message": f"Vendor {vid} does not exist"})
            continue
        if v["type"] == "customer":
            errors.append({"field": "vendorIds", "message": f"{v['code']} is a customer, not a vendor"})
        elif v["status"] != "active":
            errors.append({"field": "vendorIds", "message": f"{v['code']} is {v['status']} - only active vendors can be asked to quote"})
        else:
            found.append(v)
    if errors:
        raise rule_violation(f"Cannot invite these vendors: {'; '.join(e['message'] for e in errors)}", code="RFQ_VENDOR_INVALID", meta={"errors": errors})
    return found


def _send_request(actor: Actor, rfq: PurchaseRfq, row: PurchaseRfqVendor, lines: list[PurchaseRfqLine]) -> None:
    """Emailing is a side effect of inviting: a failure is recorded on the vendor row and never undoes the RFQ."""
    if not row.vendor_email:
        row.email_state, row.email_error = "skipped", "No email address on file for this vendor - send the request yourself, then record their quotation"
        return
    data = {
        "rfqNumber": rfq.number,
        "requisitionNumber": rfq.requisition_number or "",
        "vendorName": row.vendor_name,
        "dueDate": rfq.due_date.isoformat() if rfq.due_date else "as soon as you can",
        "requiredBy": rfq.required_by.isoformat() if rfq.required_by else "as soon as possible",
        "warehouse": rfq.warehouse_code or "",
        "terms": rfq.terms or "",
        "buyerName": _actor_name(actor),
        "lines": [{"itemName": l.item_name, "quantity": decimal_str(l.quantity), "uom": l.uom, "notes": l.notes or ""} for l in lines],
    }
    try:
        result = notification_repo.send_notification(rfq.tenant_id, template=_TEMPLATE, to=[row.vendor_email], data=data, related_type="purchase-rfq", related_id=str(rfq.id))
        row.email_state = notification_repo.delivery_state(result)
        row.email_error = result.get("error")
    except ProblemError as exc:
        row.email_state, row.email_error = "failed", exc.detail


def _invite(actor: Actor, rfq: PurchaseRfq, vendors: list[dict], *, send: bool) -> list[PurchaseRfqVendor]:
    existing = {v.vendor_id for v in sourcing_repo.vendors_of(rfq.id)}
    lines = sourcing_repo.lines_of(rfq.id)
    added = []
    for v in vendors:
        if uuid_mod.UUID(v["id"]) in existing:
            continue
        row = PurchaseRfqVendor(tenant_id=rfq.tenant_id, rfq_id=rfq.id, vendor_id=v["id"], vendor_name=v["displayName"], vendor_email=v.get("email") or None, status="invited", email_state="not_sent")
        session.add(row)
        if send:
            _send_request(actor, rfq, row, lines)
        added.append(row)
    return added


# ---- list / create / get ---------------------------------------------------------------------------------------------


@router.get("")
def list_rfqs(actor: Actor = Depends(require_permission("sourcing:read")), query: ListQuery = Depends(), status: str | None = None, requisitionId: uuid_mod.UUID | None = None):
    R = PurchaseRfq
    q = R.query.filter(R.tenant_id == actor["tenant_id"])
    if status:
        statuses = [s.strip() for s in status.split(",") if s.strip()]
        if statuses:
            q = q.filter(R.status.in_(statuses))
    if requisitionId:
        q = q.filter(R.requisition_id == requisitionId)
    if query.q:
        like = f"%{query.q}%"
        line_match = session.query(PurchaseRfqLine.rfq_id).filter(or_(PurchaseRfqLine.item_name.ilike(like), PurchaseRfqLine.sku.ilike(like)))
        vendor_match = session.query(PurchaseRfqVendor.rfq_id).filter(PurchaseRfqVendor.vendor_name.ilike(like))
        q = q.filter(or_(R.number.ilike(like), R.requisition_number.ilike(like), R.id.in_(line_match), R.id.in_(vendor_match)))
    total = q.count()
    rows = q.order_by(R.created_at.desc(), R.number.desc()).limit(query.limit).offset(offset_of(query)).all()
    summaries = sourcing_repo.list_summaries([r.id for r in rows])
    return list_response([sourcing_repo.to_api(r, summary=summaries.get(r.id)) for r in rows], query, total)


@router.post("", status_code=201)
def create_rfq(body: CreateRfqBody, actor: Actor = Depends(require_permission("sourcing:write"))):
    tenant_id = actor["tenant_id"]
    req = requisition_repo.require(tenant_id, body.requisitionId)
    if req.status != "approved":
        way = {"sourcing": "it is already out for quotation - open its RFQ", "ordered": "a purchase order already exists for it", "submitted": "Purchase has to approve it first",
               "pending_manager": "the requester's manager has to approve it first"}.get(req.status, "only an approved requisition can go out for quotation")
        raise rule_violation(f"{req.number} is {req.status}: {way}", code="RFQ_REQUISITION_NOT_APPROVED")
    vendors = _resolve_vendors(tenant_id, body.vendorIds)
    if body.dueDate and body.dueDate < date.today():
        raise rule_violation(f"The reply-by date ({body.dueDate.isoformat()}) is in the past", code="RFQ_DUE_DATE_PAST")

    warehouse_id = body.warehouseId or req.warehouse_id
    warehouse = None
    if warehouse_id:
        assert_warehouse_in_scope(actor, warehouse_id)
        warehouse = warehouse_repo.find_warehouse(tenant_id, warehouse_id)
        if not warehouse or warehouse.status != "active":
            raise rule_violation("Choose an active warehouse to deliver to", code="RFQ_WAREHOUSE_INVALID")

    rfq = PurchaseRfq(
        tenant_id=tenant_id,
        # "PRFQ", not "RFQ": logistics already numbers its carrier RFQs from that counter.
        number=next_document_number(tenant_id, "PRFQ", pad=4, start=0),
        status="open",
        requisition_id=req.id,
        requisition_number=req.number,
        warehouse_id=warehouse.id if warehouse else None,
        warehouse_code=warehouse.code if warehouse else None,
        due_date=body.dueDate,
        required_by=body.requiredBy or req.required_by,
        terms=_clean(body.terms),
        notes=_clean(body.notes),
        created_by=actor["user_id"],
        created_by_name=_actor_name(actor),
    )
    session.add(rfq)
    session.flush()
    for i, l in enumerate(requisition_repo.lines_of(req.id)):
        session.add(PurchaseRfqLine(tenant_id=tenant_id, rfq_id=rfq.id, line_no=i + 1, requisition_line_id=l.id, product_id=l.product_id, sku=l.sku, item_name=l.item_name, notes=l.notes, quantity=l.quantity, uom=l.uom))
    session.flush()
    _invite(actor, rfq, vendors, send=body.send)
    req.status = "sourcing"
    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="pr.sourcing_started", entity_type="purchase-requisition", entity_id=str(req.id), meta={"number": req.number, "status": req.status, "rfq": rfq.number})
    _audit(actor, "rfq.created", rfq, requisition=req.number, vendors=[v["displayName"] for v in vendors], emailed=body.send)
    session.commit()
    return _detail(rfq)


@router.get("/{id}")
def get_rfq(id: uuid_mod.UUID, actor: Actor = Depends(require_permission("sourcing:read"))):
    return _detail(sourcing_repo.require(actor["tenant_id"], id))


@router.get("/{id}/comparison")
def get_comparison(id: uuid_mod.UUID, actor: Actor = Depends(require_permission("sourcing:read"))):
    return sourcing_repo.comparison(sourcing_repo.require(actor["tenant_id"], id))


# ---- vendors -----------------------------------------------------------------------------------------------------------


@router.post("/{id}/vendors")
def invite_vendors(id: uuid_mod.UUID, body: InviteBody, actor: Actor = Depends(require_permission("sourcing:write"))):
    rfq = sourcing_repo.require(actor["tenant_id"], id)
    _require_open(rfq, "invite more vendors")
    added = _invite(actor, rfq, _resolve_vendors(actor["tenant_id"], body.vendorIds), send=body.send)
    _audit(actor, "rfq.vendors_added", rfq, vendors=[a.vendor_name for a in added])
    session.commit()
    return _detail(rfq)


@router.delete("/{id}/vendors/{vendor_id}")
def withdraw_vendor(id: uuid_mod.UUID, vendor_id: uuid_mod.UUID, actor: Actor = Depends(require_permission("sourcing:write"))):
    rfq = sourcing_repo.require(actor["tenant_id"], id)
    _require_open(rfq, "withdraw a vendor")
    row = _vendor_row(rfq, vendor_id)
    if PurchaseQuotation.query.filter_by(rfq_id=rfq.id, vendor_id=vendor_id).first():
        raise rule_violation(f"{row.vendor_name} has already quoted - keep the quotation on record, or record them as declined", code="RFQ_VENDOR_HAS_QUOTATION")
    session.delete(row)
    _audit(actor, "rfq.vendor_withdrawn", rfq, vendor=row.vendor_name)
    session.commit()
    return _detail(rfq)


@router.post("/{id}/vendors/{vendor_id}/resend")
def resend_request(id: uuid_mod.UUID, vendor_id: uuid_mod.UUID, actor: Actor = Depends(require_permission("sourcing:write"))):
    rfq = sourcing_repo.require(actor["tenant_id"], id)
    _require_open(rfq, "resend the request")
    row = _vendor_row(rfq, vendor_id)
    party = party_summary.build_summary_by_id(actor["tenant_id"], vendor_id)
    row.vendor_email = party.get("email") or row.vendor_email
    _send_request(actor, rfq, row, sourcing_repo.lines_of(rfq.id))
    _audit(actor, "rfq.request_resent", rfq, vendor=row.vendor_name, emailState=row.email_state)
    session.commit()
    return _detail(rfq)


@router.post("/{id}/vendors/{vendor_id}/decline")
def decline_vendor(id: uuid_mod.UUID, vendor_id: uuid_mod.UUID, actor: Actor = Depends(require_permission("sourcing:write"))):
    rfq = sourcing_repo.require(actor["tenant_id"], id)
    _require_open(rfq, "record a decline")
    row = _vendor_row(rfq, vendor_id)
    if PurchaseQuotation.query.filter_by(rfq_id=rfq.id, vendor_id=vendor_id).first():
        raise rule_violation(f"{row.vendor_name} has already quoted", code="RFQ_VENDOR_HAS_QUOTATION")
    row.status = "declined"
    _audit(actor, "rfq.vendor_declined", rfq, vendor=row.vendor_name)
    session.commit()
    return _detail(rfq)


# ---- quotations --------------------------------------------------------------------------------------------------------


@router.put("/{id}/quotations/{vendor_id}")
def record_quotation(id: uuid_mod.UUID, vendor_id: uuid_mod.UUID, body: QuotationBody, actor: Actor = Depends(require_permission("sourcing:write"))):
    tenant_id = actor["tenant_id"]
    rfq = sourcing_repo.require(tenant_id, id)
    _require_open(rfq, "record a quotation")
    vendor = _vendor_row(rfq, vendor_id)
    rfq_lines = {l.id: l for l in sourcing_repo.lines_of(rfq.id)}

    errors, seen = [], set()
    for i, ql in enumerate(body.lines):
        if ql.rfqLineId not in rfq_lines:
            errors.append({"field": f"lines.{i}.rfqLineId", "message": f"{ql.rfqLineId} is not an item on {rfq.number}"})
            continue
        if ql.rfqLineId in seen:
            errors.append({"field": f"lines.{i}.rfqLineId", "message": f"{rfq_lines[ql.rfqLineId].item_name} appears twice"})
        seen.add(ql.rfqLineId)
        if ql.unitPrice is not None and not is_known_tax_code(ql.taxCode):
            errors.append({"field": f"lines.{i}.taxCode", "message": f'"{ql.taxCode}" is not a configured tax code'})
    if not any(ql.unitPrice is not None for ql in body.lines):
        errors.append({"field": "lines", "message": "Enter a price for at least one item - or record the vendor as declined"})
    if body.quoteDate and body.validUntil and body.validUntil < body.quoteDate:
        errors.append({"field": "validUntil", "message": "Valid-until cannot be before the quotation date"})
    if errors:
        raise rule_violation(f"The quotation has {len(errors)} problem{'s' if len(errors) > 1 else ''}: {'; '.join(e['message'] for e in errors)}", code="QUOTATION_VALIDATION_FAILED", meta={"errors": errors})

    quote = PurchaseQuotation.query.filter_by(rfq_id=rfq.id, vendor_id=vendor_id).first()
    replaced = quote is not None
    if quote:
        PurchaseQuotationLine.query.filter_by(quotation_id=quote.id).delete(synchronize_session=False)
    else:
        quote = PurchaseQuotation(tenant_id=tenant_id, rfq_id=rfq.id, vendor_id=vendor_id, vendor_name=vendor.vendor_name)
        session.add(quote)
    quote.quote_ref, quote.quote_date, quote.valid_until = _clean(body.quoteRef), body.quoteDate, body.validUntil
    quote.payment_terms, quote.delivery_days, quote.charges, quote.notes = _clean(body.paymentTerms), body.deliveryDays, body.charges, _clean(body.notes)
    quote.recorded_by_name = _actor_name(actor)
    session.flush()
    for ql in body.lines:
        session.add(PurchaseQuotationLine(tenant_id=tenant_id, quotation_id=quote.id, rfq_line_id=ql.rfqLineId, unit_price=ql.unitPrice, tax_code=ql.taxCode or "GST0", lead_time_days=ql.leadTimeDays, notes=_clean(ql.notes)))
    vendor.status = "quoted"
    _audit(actor, "rfq.quotation_recorded", rfq, vendor=vendor.vendor_name, replaced=replaced, quotedLines=sum(1 for ql in body.lines if ql.unitPrice is not None))
    session.commit()
    return _detail(rfq)


# ---- award -------------------------------------------------------------------------------------------------------------


def _assert_no_orders(rfq: PurchaseRfq, doing: str) -> None:
    if PurchaseRfqLine.query.filter(PurchaseRfqLine.rfq_id == rfq.id, PurchaseRfqLine.purchase_order_id.isnot(None)).first():
        raise rule_violation(f"{rfq.number} already has purchase orders, so you cannot {doing}", code="RFQ_HAS_ORDERS")


@router.post("/{id}/award")
def award(id: uuid_mod.UUID, body: AwardBody, actor: Actor = Depends(require_permission("sourcing:award"))):
    tenant_id = actor["tenant_id"]
    rfq = sourcing_repo.require(tenant_id, id)
    if rfq.status not in ("open", "awarded"):
        raise rule_violation(f"{rfq.number} is {rfq.status}, so it cannot be awarded", code="RFQ_INVALID_STATE")
    _assert_no_orders(rfq, "change the award")
    comp = sourcing_repo.comparison(rfq)
    by_line = {l["rfqLineId"]: l for l in comp["lines"]}
    rfq_lines = {str(l.id): l for l in sourcing_repo.lines_of(rfq.id)}

    errors, chosen = [], {}
    for i, a in enumerate(body.awards):
        lid, vid = str(a.rfqLineId), str(a.vendorId)
        info = by_line.get(lid)
        if not info:
            errors.append({"field": f"awards.{i}", "message": f"{lid} is not an item on {rfq.number}"})
            continue
        if lid in chosen:
            errors.append({"field": f"awards.{i}", "message": f"{info['itemName']} is awarded twice"})
            continue
        offer = info["offers"].get(vid)
        if not offer:
            errors.append({"field": f"awards.{i}", "message": f"That vendor did not quote {info['itemName']}"})
            continue
        # A choice that is not simply "the lowest price from a real choice of quotes" has to be explained.
        reason = _clean(a.reason)
        why = []
        if not offer["isLowest"]:
            why.append("it is not the lowest price")
        if info["quoteCount"] < 2:
            why.append("only one vendor quoted it")
        if offer["expired"]:
            why.append("the quotation has expired")
        if why and (not reason or len(reason) < 3):
            errors.append({"field": f"awards.{i}.reason", "message": f"Give a reason for {info['itemName']}: {' and '.join(why)}"})
        chosen[lid] = (vid, reason)
    quoted_but_unawarded = [l["itemName"] for l in comp["lines"] if l["offers"] and l["rfqLineId"] not in chosen]
    if quoted_but_unawarded:
        errors.append({"field": "awards", "message": f"Choose a vendor for: {', '.join(quoted_but_unawarded)}"})
    if errors:
        raise rule_violation(f"The award has {len(errors)} problem{'s' if len(errors) > 1 else ''}: {'; '.join(e['message'] for e in errors)}", code="AWARD_VALIDATION_FAILED", meta={"errors": errors})

    for lid, line in rfq_lines.items():
        vid, reason = chosen.get(lid, (None, None))
        line.awarded_vendor_id = uuid_mod.UUID(vid) if vid else None
        line.award_reason = reason
    rfq.status = "awarded"
    rfq.awarded_by_name = _actor_name(actor)
    rfq.awarded_at = datetime.now(timezone.utc)
    _audit(actor, "rfq.awarded", rfq, awards=[{"item": by_line[l]["itemName"], "vendorId": v, "reason": r} for l, (v, r) in chosen.items()])
    session.commit()
    return _detail(rfq)


@router.post("/{id}/reopen")
def reopen(id: uuid_mod.UUID, actor: Actor = Depends(require_permission("sourcing:award"))):
    rfq = sourcing_repo.require(actor["tenant_id"], id)
    if rfq.status != "awarded":
        raise rule_violation(f"{rfq.number} is {rfq.status}; only an awarded RFQ can be reopened", code="RFQ_INVALID_STATE")
    _assert_no_orders(rfq, "reopen it")
    for line in sourcing_repo.lines_of(rfq.id):
        line.awarded_vendor_id, line.award_reason = None, None
    rfq.status, rfq.awarded_by_name, rfq.awarded_at = "open", None, None
    _audit(actor, "rfq.reopened", rfq)
    session.commit()
    return _detail(rfq)


# ---- purchase orders -----------------------------------------------------------------------------------------------------


@router.post("/{id}/purchase-orders")
def create_purchase_orders(id: uuid_mod.UUID, body: CreatePosBody, actor: Actor = Depends(require_permission("sourcing:award", "po:write"))):
    """One purchase order per winning vendor, priced from that vendor's quotation. Each order and its link back to the RFQ
    are committed together, so running this again after a failure only raises the orders that are still missing."""
    tenant_id = actor["tenant_id"]
    rfq = sourcing_repo.require(tenant_id, id)
    if rfq.status != "awarded":
        raise rule_violation(f"{rfq.number} is {rfq.status}: award it first, then raise the purchase orders", code="RFQ_INVALID_STATE")
    warehouse_id = body.warehouseId or rfq.warehouse_id
    if not warehouse_id:
        raise rule_violation("Choose where the goods are delivered to - the requisition did not say", code="RFQ_WAREHOUSE_REQUIRED")

    lines = sourcing_repo.lines_of(rfq.id)
    quotes = sourcing_repo.quotations_of(rfq.id)
    today = date.today()
    groups: dict[uuid_mod.UUID, list[PurchaseRfqLine]] = defaultdict(list)
    skipped = []
    for l in lines:
        if not l.awarded_vendor_id or l.purchase_order_id:
            continue
        if not l.product_id:
            skipped.append(l.item_name)  # a free-text item has no product to order yet
            continue
        groups[l.awarded_vendor_id].append(l)

    created = []
    for vendor_id, vlines in groups.items():
        quote, qlines = quotes[vendor_id]
        lead = max([qlines[l.id].lead_time_days or 0 for l in vlines] + [quote.delivery_days or 0])
        expected = body.expectedDate or max(rfq.required_by or today, today + timedelta(days=lead))
        po_body = PoBody(
            vendorId=vendor_id,
            warehouseId=warehouse_id,
            expectedDate=max(expected, today),
            paymentTerms=quote.payment_terms,
            charges=decimal_str(quote.charges),
            notes=f"Raised from RFQ {rfq.number} ({rfq.requisition_number}), quotation {quote.quote_ref or 'on file'}"[:2000],
            lines=[LineBody(productId=l.product_id, description=l.item_name, quantity=decimal_str(l.quantity), uom=l.uom, unitPrice=decimal_str(qlines[l.id].unit_price), taxCode=qlines[l.id].tax_code) for l in vlines],
        )
        vline_ids = [l.id for l in vlines]

        def link(po, vline_ids=vline_ids):
            PurchaseRfqLine.query.filter(PurchaseRfqLine.id.in_(vline_ids)).update({"purchase_order_id": po.id, "purchase_order_number": po.number}, synchronize_session=False)
            session.flush()
            session.expire_all()
            _audit(actor, "rfq.po_created", sourcing_repo.require(tenant_id, rfq.id), purchaseOrder=po.number, vendorId=str(vendor_id))
            _finish_if_fully_ordered(rfq)

        po = _create_po_postgres(tenant_id, actor, po_body, before_commit=link)
        created.append({"id": str(po.id), "number": po.number, "vendorId": str(vendor_id)})

    if not created and not skipped:
        raise rule_violation(f"Every awarded item on {rfq.number} already has a purchase order", code="RFQ_NOTHING_TO_ORDER")
    result = _detail(sourcing_repo.require(tenant_id, id))
    result["created"] = created
    result["skippedFreeTextItems"] = skipped
    return result


def _finish_if_fully_ordered(rfq: PurchaseRfq) -> None:
    """Called inside the transaction that links the last purchase order: the RFQ and its requisition move on to ordered."""
    rfq = sourcing_repo.require(rfq.tenant_id, rfq.id)
    lines = sourcing_repo.lines_of(rfq.id)
    outstanding = [l for l in lines if l.awarded_vendor_id and l.product_id and not l.purchase_order_id]
    if outstanding:
        return
    rfq.status = "ordered"
    if rfq.requisition_id:
        req = requisition_repo.find(rfq.tenant_id, rfq.requisition_id)
        if req and req.status in ("sourcing", "approved"):
            numbers = sorted({l.purchase_order_number for l in lines if l.purchase_order_number})
            first = next((l.purchase_order_id for l in lines if l.purchase_order_id), None)
            req.status, req.purchase_order_id, req.purchase_order_number = "ordered", first, ", ".join(numbers)


# ---- cancel --------------------------------------------------------------------------------------------------------------


@router.post("/{id}/cancel")
def cancel_rfq(id: uuid_mod.UUID, body: CancelBody, actor: Actor = Depends(require_permission("sourcing:write"))):
    rfq = sourcing_repo.require(actor["tenant_id"], id)
    if rfq.status not in ("open", "awarded"):
        raise rule_violation(f"{rfq.number} is {rfq.status} and cannot be cancelled", code="RFQ_INVALID_STATE")
    _assert_no_orders(rfq, "cancel it")
    rfq.status = "cancelled"
    rfq.cancelled_reason = body.reason.strip()
    rfq.cancelled_at = datetime.now(timezone.utc)
    if rfq.requisition_id:
        req = requisition_repo.find(actor["tenant_id"], rfq.requisition_id)
        if req and req.status == "sourcing":
            req.status = "approved"
    _audit(actor, "rfq.cancelled", rfq, reason=rfq.cancelled_reason)
    session.commit()
    return _detail(rfq)
