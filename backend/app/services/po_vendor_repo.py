"""After the PO is issued: what the vendor sent back (acknowledgement, documents) and what they shipped (dispatches).

  issued -> vendor acknowledges -> vendor documents (proforma, technical...) -> dispatch documentation -> GRN

The buyer records these from the vendor's emails and papers; there is no vendor login. A dispatch is marked delivered by hand,
or automatically when goods receipts against the PO cover it (see `reconcile`)."""

from __future__ import annotations

import re
import uuid
from collections import defaultdict
from datetime import date
from decimal import Decimal

from app.core.db import session
from app.core.errors import not_found
from app.core.money import decimal_str, to_decimal
from app.models.po_line import PoLine
from app.models.po_vendor import PoDispatch, PoDispatchLine, PoDocument

ACK_STATUSES = ("pending", "acknowledged", "acknowledged_with_changes", "declined")

VENDOR_DOC_TYPES = {
    "po_acknowledgement": "PO acknowledgement",
    "proforma_invoice": "Proforma invoice",
    "technical_document": "Technical document",
    "test_certificate": "Test / quality certificate",
    "other": "Other document",
}
DISPATCH_DOC_TYPES = {
    "packing_list": "Packing list",
    "delivery_challan": "Delivery challan",
    "eway_bill": "E-way bill",
    "transport_document": "Transport document (LR / AWB / BL)",
    "tax_invoice": "Tax invoice",
    "other": "Other document",
}
DOC_TYPES = {**VENDOR_DOC_TYPES, **DISPATCH_DOC_TYPES}

# An e-way bill is normally required to move goods worth more than this (INR) - a warning, never a block, since it depends
# on the goods, the states involved and exemptions.
EWAY_BILL_THRESHOLD = Decimal("50000")

EWAY_RE = re.compile(r"^\d{12}$")
VEHICLE_RE = re.compile(r"^[A-Z0-9][A-Z0-9 -]{2,19}$")
PHONE_RE = re.compile(r"^\+?[0-9][0-9 ()-]{6,19}$")


def find_dispatch(tenant_id: uuid.UUID, po_id: uuid.UUID, dispatch_id: uuid.UUID) -> PoDispatch | None:
    return PoDispatch.query.filter_by(tenant_id=tenant_id, po_id=po_id, id=dispatch_id).first()


def require_dispatch(tenant_id: uuid.UUID, po_id: uuid.UUID, dispatch_id: uuid.UUID) -> PoDispatch:
    row = find_dispatch(tenant_id, po_id, dispatch_id)
    if not row:
        raise not_found("Dispatch")
    return row


def dispatches_of(po_id: uuid.UUID) -> list[PoDispatch]:
    return PoDispatch.query.filter_by(po_id=po_id).order_by(PoDispatch.dispatch_date, PoDispatch.created_at).all()


def dispatch_lines(dispatch_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[PoDispatchLine]]:
    out: dict[uuid.UUID, list[PoDispatchLine]] = defaultdict(list)
    if dispatch_ids:
        for l in PoDispatchLine.query.filter(PoDispatchLine.dispatch_id.in_(dispatch_ids)).all():
            out[l.dispatch_id].append(l)
    return out


def documents_of(po_id: uuid.UUID) -> list[PoDocument]:
    return PoDocument.query.filter_by(po_id=po_id).order_by(PoDocument.uploaded_at).all()


def in_transit_qty(po_id: uuid.UUID) -> dict[uuid.UUID, Decimal]:
    """Quantity per PO line that has been dispatched but not yet received."""
    out: dict[uuid.UUID, Decimal] = defaultdict(Decimal)
    rows = (
        session.query(PoDispatchLine.po_line_id, PoDispatchLine.quantity)
        .join(PoDispatch, PoDispatch.id == PoDispatchLine.dispatch_id)
        .filter(PoDispatch.po_id == po_id, PoDispatch.status == "in_transit")
        .all()
    )
    for line_id, qty in rows:
        out[line_id] += to_decimal(qty)
    return out


def dispatchable_qty(lines: list[PoLine], po_id: uuid.UUID, *, exclude_dispatch: uuid.UUID | None = None) -> dict[uuid.UUID, Decimal]:
    """What the vendor may still ship per line: ordered, less what has been received, rejected or is already on the road."""
    transit: dict[uuid.UUID, Decimal] = defaultdict(Decimal)
    rows = (
        session.query(PoDispatchLine.po_line_id, PoDispatchLine.quantity)
        .join(PoDispatch, PoDispatch.id == PoDispatchLine.dispatch_id)
        .filter(PoDispatch.po_id == po_id, PoDispatch.status == "in_transit", PoDispatch.id != (exclude_dispatch or uuid.UUID(int=0)))
        .all()
    )
    for line_id, qty in rows:
        transit[line_id] += to_decimal(qty)
    out = {}
    for l in lines:
        left = to_decimal(l.quantity) - to_decimal(l.received_qty) - to_decimal(l.rejected_qty) - transit[l.id]
        out[l.id] = left if left > 0 else Decimal(0)
    return out


def reconcile(tenant_id: uuid.UUID, po_id: uuid.UUID) -> None:
    """Keeps shipment status in step with goods receipts (runs inside the GRN transaction, both ways).

    Goods received against a PO line are shared out over that line's shipments, oldest first; a shipment whose every line is
    covered is delivered, and one that stops being covered (a GRN was cancelled) goes back in transit. A shipment someone
    marked delivered by hand keeps its status but still uses up its share."""
    lines = {l.id: l for l in PoLine.query.filter_by(po_id=po_id).all()}
    pool = {lid: to_decimal(l.received_qty) + to_decimal(l.rejected_qty) for lid, l in lines.items()}
    dispatches = [d for d in dispatches_of(po_id) if d.status != "cancelled"]
    by_dispatch = dispatch_lines([d.id for d in dispatches])
    for d in dispatches:
        need = {l.po_line_id: to_decimal(l.quantity) for l in by_dispatch.get(d.id, [])}
        manual_delivered = d.status == "delivered" and not d.auto_delivered
        covered = all(pool.get(lid, Decimal(0)) >= q for lid, q in need.items()) and bool(need)
        # Whatever has been received goes to the oldest shipment first, even if that only part-covers it.
        for lid, q in need.items():
            pool[lid] = max(Decimal(0), pool.get(lid, Decimal(0)) - q)
        if manual_delivered:
            continue
        if covered and d.status == "in_transit":
            d.status, d.auto_delivered, d.delivered_at = "delivered", True, _now()
        elif not covered and d.status == "delivered" and d.auto_delivered:
            d.status, d.auto_delivered, d.delivered_at = "in_transit", False, None


def _now():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)


def _iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


def document_to_api(d: PoDocument) -> dict:
    return {
        "id": str(d.id),
        "dispatchId": str(d.dispatch_id) if d.dispatch_id else None,
        "docType": d.doc_type,
        "docTypeLabel": DOC_TYPES.get(d.doc_type, d.doc_type),
        "stage": "dispatch" if d.dispatch_id else "vendor",
        "referenceNo": d.reference_no,
        "description": d.description,
        "filename": d.filename,
        "contentType": d.content_type,
        "bytes": d.bytes_,
        "uploadedByName": d.uploaded_by_name,
        "uploadedAt": d.uploaded_at.isoformat() if d.uploaded_at else None,
    }


def dispatch_value(lines: list[PoDispatchLine], po_lines: dict[uuid.UUID, PoLine]) -> Decimal:
    """What a shipment is worth at the PO's prices, tax included."""
    total = Decimal(0)
    for l in lines:
        pl = po_lines.get(l.po_line_id)
        if not pl:
            continue
        unit_gross = to_decimal(pl.gross_amount) / to_decimal(pl.quantity) if to_decimal(pl.quantity) else Decimal(0)
        total += unit_gross * to_decimal(l.quantity)
    return total


def eway_warning(d: PoDispatch, lines: list[PoDispatchLine], po_lines: dict[uuid.UUID, PoLine]) -> str | None:
    if d.eway_bill_no:
        return None
    value = to_decimal(d.invoice_value) if d.invoice_value is not None else dispatch_value(lines, po_lines)
    if value > EWAY_BILL_THRESHOLD:
        return f"This consignment is worth about {decimal_str(value.quantize(Decimal('0.01')))}; goods above {EWAY_BILL_THRESHOLD:,.0f} normally need an e-way bill. Record its number if the vendor has generated one."
    return None


def dispatch_to_api(d: PoDispatch, lines: list[PoDispatchLine], po_lines: dict[uuid.UUID, PoLine], docs: list[PoDocument]) -> dict:
    today = date.today()
    return {
        "id": str(d.id),
        "number": d.number,
        "status": d.status,
        "dispatchDate": _iso(d.dispatch_date),
        "expectedArrival": _iso(d.expected_arrival),
        "overdue": bool(d.status == "in_transit" and d.expected_arrival and d.expected_arrival < today),
        "transporter": d.transporter,
        "vehicleNo": d.vehicle_no,
        "lrNo": d.lr_no,
        "driverName": d.driver_name,
        "driverPhone": d.driver_phone,
        "packages": d.packages,
        "grossWeightKg": decimal_str(d.gross_weight_kg) if d.gross_weight_kg is not None else None,
        "invoiceNo": d.invoice_no,
        "invoiceDate": _iso(d.invoice_date),
        "invoiceValue": decimal_str(d.invoice_value) if d.invoice_value is not None else None,
        "packingListNo": d.packing_list_no,
        "deliveryChallanNo": d.delivery_challan_no,
        "deliveryChallanDate": _iso(d.delivery_challan_date),
        "ewayBillNo": d.eway_bill_no,
        "ewayBillValidUntil": _iso(d.eway_bill_valid_until),
        "ewayBillExpired": bool(d.eway_bill_valid_until and d.status == "in_transit" and d.eway_bill_valid_until < today),
        "warning": eway_warning(d, lines, po_lines) if d.status == "in_transit" else None,
        "notes": d.notes,
        "deliveredAt": d.delivered_at.isoformat() if d.delivered_at else None,
        "autoDelivered": d.auto_delivered,
        "cancelledReason": d.cancelled_reason,
        "recordedByName": d.recorded_by_name,
        "lines": [
            {
                "poLineId": str(l.po_line_id),
                "sku": po_lines[l.po_line_id].sku if l.po_line_id in po_lines else None,
                "itemName": (po_lines[l.po_line_id].description or po_lines[l.po_line_id].sku) if l.po_line_id in po_lines else None,
                "quantity": decimal_str(l.quantity),
                "uom": po_lines[l.po_line_id].uom if l.po_line_id in po_lines else None,
            }
            for l in lines
        ],
        "documents": [document_to_api(x) for x in docs],
    }


def ack_to_api(po) -> dict:
    return {
        "status": po.ack_status,
        "date": _iso(po.ack_date),
        "ref": po.ack_ref,
        "confirmedDate": _iso(po.ack_confirmed_date),
        "notes": po.ack_notes,
        "recordedBy": po.ack_recorded_by,
        "recordedAt": po.ack_recorded_at.isoformat() if po.ack_recorded_at else None,
    }


def summaries(po_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict]:
    """documentCount (the vendor's own documents; shipment papers count under their dispatch) + shipment state per PO, for a page of POs in three queries."""
    out = {i: {"documentCount": 0, "dispatchCount": 0, "dispatchStatus": "none", "inTransitCount": 0} for i in po_ids}
    if not po_ids:
        return out
    for (po_id,) in session.query(PoDocument.po_id).filter(PoDocument.po_id.in_(po_ids), PoDocument.dispatch_id.is_(None)).all():
        out[po_id]["documentCount"] += 1
    for po_id, status in session.query(PoDispatch.po_id, PoDispatch.status).filter(PoDispatch.po_id.in_(po_ids), PoDispatch.status != "cancelled").all():
        o = out[po_id]
        o["dispatchCount"] += 1
        if status == "in_transit":
            o["inTransitCount"] += 1
    for o in out.values():
        o["dispatchStatus"] = "in_transit" if o["inTransitCount"] else "delivered" if o["dispatchCount"] else "none"
    return out
