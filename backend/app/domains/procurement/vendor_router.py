"""Purchase orders, after issue: vendor acknowledgement, vendor documents and dispatch documentation.

GET    /api/v1/purchase-orders/{id}/vendor-tracking                 acknowledgement, documents and shipments in one call
PUT    /api/v1/purchase-orders/{id}/acknowledgement                 record the vendor's reply (acknowledged / with changes / declined)
DELETE /api/v1/purchase-orders/{id}/acknowledgement                 back to "waiting for the vendor"
POST   /api/v1/purchase-orders/{id}/documents                       attach a file the vendor sent (base64, like /documents/upload)
GET    /api/v1/purchase-orders/{id}/documents/{docId}/download
DELETE /api/v1/purchase-orders/{id}/documents/{docId}
POST   /api/v1/purchase-orders/{id}/dispatches                      record a shipment: transport, e-way bill, packing list, challan, items
PATCH  /api/v1/purchase-orders/{id}/dispatches/{dispatchId}         correct a shipment that is still in transit
POST   /api/v1/purchase-orders/{id}/dispatches/{dispatchId}/deliver   goods have arrived (GRN receipts also do this automatically)
POST   /api/v1/purchase-orders/{id}/dispatches/{dispatchId}/cancel

Reading needs po:read (or warehouse:read, so the receiving team sees what is coming); recording needs po:vendor.
"""

from __future__ import annotations

import uuid as uuid_mod
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, Field

from app.core.access_scope import assert_warehouse_in_scope
from app.core.audit import audit
from app.core.auth import Actor, require_any_permission, require_permission
from app.core.db import session
from app.core.errors import conflict, rule_violation
from app.core.money import decimal_str, to_decimal
from app.core.scalars import DecimalString
from app.models.po_vendor import PoDispatch, PoDispatchLine, PoDocument
from app.models.purchase_order import PurchaseOrder
from app.services import document_repo, document_storage, po_vendor_repo as repo, procurement_repo

router = APIRouter(prefix="/api/v1/purchase-orders", tags=["procurement"])

_READ = ("po:read", "warehouse:read")
_OPEN_STATUSES = ("issued", "partially_received")


class AckBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    ackDate: date | None = None
    ackRef: str | None = Field(default=None, max_length=80)
    confirmedDate: date | None = None
    notes: str | None = Field(default=None, max_length=2000)


class DocumentBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    docType: str
    filename: str = Field(min_length=1, max_length=200)
    contentType: str = Field(min_length=3, max_length=120)
    contentBase64: str = Field(min_length=1)
    referenceNo: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    dispatchId: uuid_mod.UUID | None = None


class DispatchLineBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    poLineId: uuid_mod.UUID
    quantity: DecimalString


class DispatchFields(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dispatchDate: date | None = None
    expectedArrival: date | None = None
    transporter: str | None = Field(default=None, max_length=120)
    vehicleNo: str | None = Field(default=None, max_length=30)
    lrNo: str | None = Field(default=None, max_length=60)
    driverName: str | None = Field(default=None, max_length=120)
    driverPhone: str | None = Field(default=None, max_length=30)
    packages: int | None = Field(default=None, ge=1, le=1_000_000)
    grossWeightKg: DecimalString | None = None
    invoiceNo: str | None = Field(default=None, max_length=60)
    invoiceDate: date | None = None
    invoiceValue: DecimalString | None = None
    packingListNo: str | None = Field(default=None, max_length=60)
    deliveryChallanNo: str | None = Field(default=None, max_length=60)
    deliveryChallanDate: date | None = None
    ewayBillNo: str | None = Field(default=None, max_length=20)
    ewayBillValidUntil: date | None = None
    notes: str | None = Field(default=None, max_length=2000)


class DispatchBody(DispatchFields):
    dispatchDate: date
    lines: list[DispatchLineBody] = Field(min_length=1, max_length=200)


class DispatchPatch(DispatchFields):
    lines: list[DispatchLineBody] | None = Field(default=None, min_length=1, max_length=200)


class ReasonBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=3, max_length=1000)


class NoteBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    notes: str | None = Field(default=None, max_length=1000)


def _name(actor: Actor) -> str:
    return actor.get("name") or actor.get("email") or "Unknown user"


def _clean(v: str | None) -> str | None:
    v = (v or "").strip()
    return v or None


def _po(actor: Actor, po_id) -> PurchaseOrder:
    po = procurement_repo.require_po(actor["tenant_id"], po_id)
    assert_warehouse_in_scope(actor, po.warehouse_id)
    return po


def _require_live(po: PurchaseOrder, doing: str) -> None:
    if po.status not in _OPEN_STATUSES:
        raise rule_violation(f"{po.number} is {po.status}, so you cannot {doing}: vendor tracking applies to an issued order that is still being delivered", code="PO_NOT_OPEN")


def _audit(actor: Actor, action: str, po: PurchaseOrder, reason: str | None = None, **meta) -> None:
    audit(tenant_id=actor["tenant_id"], actor_id=actor["user_id"], actor_email=actor["email"], action=action, entity_type="purchase-order", entity_id=str(po.id), reason=reason, meta={"number": po.number, **meta})


def tracking(po: PurchaseOrder) -> dict:
    lines = procurement_repo.lines_of(po.id)
    po_lines = {l.id: l for l in lines}
    docs = repo.documents_of(po.id)
    dispatches = repo.dispatches_of(po.id)
    dl = repo.dispatch_lines([d.id for d in dispatches])
    room = repo.dispatchable_qty(lines, po.id)
    return {
        "poId": str(po.id),
        "poNumber": po.number,
        "poStatus": po.status,
        "expectedDate": po.expected_date.isoformat() if po.expected_date else None,
        "acknowledgement": repo.ack_to_api(po),
        "documents": [repo.document_to_api(d) for d in docs if d.dispatch_id is None],
        "dispatches": [repo.dispatch_to_api(d, dl.get(d.id, []), po_lines, [x for x in docs if x.dispatch_id == d.id]) for d in dispatches],
        "dispatchable": [
            {"poLineId": str(l.id), "sku": l.sku, "itemName": l.description or l.sku, "uom": l.uom, "ordered": decimal_str(l.quantity), "received": decimal_str(l.received_qty), "rejected": decimal_str(l.rejected_qty),
             "inTransit": decimal_str(repo.in_transit_qty(po.id).get(l.id, 0)), "canDispatch": decimal_str(room[l.id])}
            for l in lines
        ],
        "docTypes": {"vendor": repo.VENDOR_DOC_TYPES, "dispatch": repo.DISPATCH_DOC_TYPES},
    }


@router.get("/{id}/vendor-tracking")
def get_tracking(id: uuid_mod.UUID, actor: Actor = Depends(require_any_permission(*_READ))):
    return tracking(_po(actor, id))


# ---- acknowledgement -------------------------------------------------------------------------------------------------


@router.put("/{id}/acknowledgement")
def put_ack(id: uuid_mod.UUID, body: AckBody, actor: Actor = Depends(require_permission("po:vendor"))):
    po = _po(actor, id)
    _require_live(po, "record an acknowledgement")
    if body.status not in ("acknowledged", "acknowledged_with_changes", "declined"):
        raise rule_violation('Status must be "acknowledged", "acknowledged_with_changes" or "declined"', code="ACK_STATUS_INVALID")
    notes = _clean(body.notes)
    if body.status != "acknowledged" and not notes:
        raise rule_violation("Say what the vendor changed, or why they declined - it is kept with the order", code="ACK_NOTES_REQUIRED")
    if body.status == "acknowledged_with_changes" and not body.confirmedDate and not notes:
        raise rule_violation("Record the changes: a new delivery date, or a note about what differs", code="ACK_NOTES_REQUIRED")
    ack_date = body.ackDate or date.today()
    if ack_date > date.today():
        raise rule_violation(f"The acknowledgement date ({ack_date.isoformat()}) is in the future", code="ACK_DATE_FUTURE")
    if ack_date < po.po_date:
        raise rule_violation(f"The vendor cannot acknowledge on {ack_date.isoformat()}, before the order date {po.po_date.isoformat()}", code="ACK_DATE_BEFORE_PO")
    if body.confirmedDate and body.confirmedDate < ack_date:
        raise rule_violation("The delivery date the vendor confirmed cannot be before they acknowledged", code="ACK_DELIVERY_DATE_INVALID")
    before = po.ack_status
    po.ack_status, po.ack_date, po.ack_ref = body.status, ack_date, _clean(body.ackRef)
    po.ack_confirmed_date, po.ack_notes = body.confirmedDate, notes
    po.ack_recorded_by, po.ack_recorded_at = _name(actor), datetime.now(timezone.utc)
    _audit(actor, "po.acknowledged", po, reason=notes, status=body.status, before=before, confirmedDate=body.confirmedDate.isoformat() if body.confirmedDate else None)
    session.commit()
    return tracking(po)


@router.delete("/{id}/acknowledgement")
def clear_ack(id: uuid_mod.UUID, actor: Actor = Depends(require_permission("po:vendor"))):
    po = _po(actor, id)
    _require_live(po, "clear the acknowledgement")
    before = po.ack_status
    po.ack_status, po.ack_date, po.ack_ref, po.ack_confirmed_date, po.ack_notes = "pending", None, None, None, None
    po.ack_recorded_by, po.ack_recorded_at = None, None
    _audit(actor, "po.acknowledgement_cleared", po, before=before)
    session.commit()
    return tracking(po)


# ---- documents ---------------------------------------------------------------------------------------------------------


@router.post("/{id}/documents", status_code=201)
def add_document(id: uuid_mod.UUID, body: DocumentBody, actor: Actor = Depends(require_permission("po:vendor"))):
    tenant_id = actor["tenant_id"]
    po = _po(actor, id)
    if po.status in ("cancelled", "draft"):
        raise rule_violation(f"{po.number} is {po.status}, so documents cannot be added to it", code="PO_NOT_OPEN")
    if body.docType not in repo.DOC_TYPES:
        raise rule_violation(f'"{body.docType}" is not a document type - use one of {", ".join(repo.DOC_TYPES)}', code="DOC_TYPE_INVALID")
    dispatch = None
    if body.dispatchId:
        dispatch = repo.require_dispatch(tenant_id, po.id, body.dispatchId)
        if body.docType not in repo.DISPATCH_DOC_TYPES:
            raise rule_violation(f"{repo.DOC_TYPES[body.docType]} belongs to the order, not to a shipment", code="DOC_TYPE_INVALID")
    elif body.docType in repo.DISPATCH_DOC_TYPES and body.docType != "other":
        raise rule_violation(f"{repo.DOC_TYPES[body.docType]} belongs to a shipment: record the dispatch first, then attach it there", code="DOC_NEEDS_DISPATCH")
    stored = document_repo.upload_document(
        tenant_id, filename=body.filename, content_type=body.contentType, content_base64=body.contentBase64,
        related_type="purchase-order", related_id=str(po.id), created_by=str(actor["user_id"]),
    )
    row = PoDocument(
        tenant_id=tenant_id, po_id=po.id, dispatch_id=dispatch.id if dispatch else None, document_id=uuid_mod.UUID(stored["id"]), doc_type=body.docType,
        reference_no=_clean(body.referenceNo), description=_clean(body.description), filename=stored["filename"], content_type=body.contentType,
        bytes_=stored.get("bytes", 0), uploaded_by=actor["user_id"], uploaded_by_name=_name(actor),
    )
    session.add(row)
    session.flush()
    _audit(actor, "po.document_added", po, docType=body.docType, filename=row.filename, dispatch=dispatch.number if dispatch else None)
    session.commit()
    return repo.document_to_api(row)


def _doc(actor: Actor, po: PurchaseOrder, doc_id) -> PoDocument:
    row = PoDocument.query.filter_by(tenant_id=actor["tenant_id"], po_id=po.id, id=doc_id).first()
    if not row:
        from app.core.errors import not_found

        raise not_found("Document")
    return row


@router.get("/{id}/documents/{doc_id}/download")
def download_document(id: uuid_mod.UUID, doc_id: uuid_mod.UUID, actor: Actor = Depends(require_any_permission(*_READ))):
    po = _po(actor, id)
    row = _doc(actor, po, doc_id)
    stored = document_repo.require_document(actor["tenant_id"], row.document_id)
    if stored.scan_status == "infected":
        raise conflict(f"{row.filename} failed a malware scan and cannot be downloaded", code="DOCUMENT_INFECTED")
    try:
        data = document_storage.get(stored.storage_key)
    except FileNotFoundError:
        raise conflict(f"{row.filename} is no longer available in storage", code="DOCUMENT_FILE_MISSING")
    disposition = "inline" if row.content_type == "application/pdf" else "attachment"
    return Response(content=data, media_type=row.content_type, headers={"Content-Disposition": f'{disposition}; filename="{row.filename}"'})


@router.delete("/{id}/documents/{doc_id}")
def delete_document(id: uuid_mod.UUID, doc_id: uuid_mod.UUID, actor: Actor = Depends(require_permission("po:vendor"))):
    po = _po(actor, id)
    row = _doc(actor, po, doc_id)
    _audit(actor, "po.document_removed", po, docType=row.doc_type, filename=row.filename)
    session.delete(row)
    session.commit()
    return tracking(po)


# ---- dispatches --------------------------------------------------------------------------------------------------------


def _validate_fields(f: DispatchFields, *, dispatch_date: date | None) -> dict:
    """Normalised, checked header fields; every problem reported together."""
    errors = []
    data = {k: _clean(v) if isinstance(v, str) else v for k, v in f.model_dump(exclude={"lines"}).items()}
    if data.get("vehicleNo"):
        data["vehicleNo"] = data["vehicleNo"].upper()
        if not repo.VEHICLE_RE.match(data["vehicleNo"]):
            errors.append({"field": "vehicleNo", "message": "Vehicle number should be letters and digits, e.g. MH12AB1234"})
    if data.get("ewayBillNo"):
        data["ewayBillNo"] = data["ewayBillNo"].replace(" ", "")
        if not repo.EWAY_RE.match(data["ewayBillNo"]):
            errors.append({"field": "ewayBillNo", "message": "An e-way bill number is 12 digits"})
    if data.get("driverPhone") and not repo.PHONE_RE.match(data["driverPhone"]):
        errors.append({"field": "driverPhone", "message": "Driver phone does not look like a phone number"})
    if dispatch_date:
        if dispatch_date > date.today():
            errors.append({"field": "dispatchDate", "message": f"Dispatch date ({dispatch_date.isoformat()}) is in the future - record it when the goods leave"})
        if data.get("expectedArrival") and data["expectedArrival"] < dispatch_date:
            errors.append({"field": "expectedArrival", "message": "Expected arrival cannot be before the dispatch date"})
        if data.get("ewayBillValidUntil") and data["ewayBillValidUntil"] < dispatch_date:
            errors.append({"field": "ewayBillValidUntil", "message": "The e-way bill cannot expire before the dispatch date"})
        if data.get("deliveryChallanDate") and data["deliveryChallanDate"] > date.today():
            errors.append({"field": "deliveryChallanDate", "message": "The delivery challan date is in the future"})
    if data.get("ewayBillValidUntil") and not data.get("ewayBillNo"):
        errors.append({"field": "ewayBillNo", "message": "Enter the e-way bill number that goes with the validity date"})
    if errors:
        raise rule_violation(f"The dispatch has {len(errors)} problem{'s' if len(errors) > 1 else ''}: {'; '.join(e['message'] for e in errors)}", code="DISPATCH_VALIDATION_FAILED", meta={"errors": errors})
    return data


def _validate_lines(po: PurchaseOrder, lines: list[DispatchLineBody], *, exclude: uuid_mod.UUID | None = None) -> list[tuple[uuid_mod.UUID, str]]:
    po_lines = procurement_repo.lines_of(po.id)
    room = repo.dispatchable_qty(po_lines, po.id, exclude_dispatch=exclude)
    by_id = {l.id: l for l in po_lines}
    errors, seen, out = [], set(), []
    for i, l in enumerate(lines):
        pl = by_id.get(l.poLineId)
        if not pl:
            errors.append({"field": f"lines.{i}.poLineId", "message": f"{l.poLineId} is not an item on {po.number}"})
            continue
        if l.poLineId in seen:
            errors.append({"field": f"lines.{i}", "message": f"{pl.sku} appears twice"})
        seen.add(l.poLineId)
        qty = to_decimal(l.quantity)
        if qty <= 0:
            errors.append({"field": f"lines.{i}.quantity", "message": f"{pl.sku}: quantity must be more than zero"})
        elif qty > room[pl.id]:
            errors.append({"field": f"lines.{i}.quantity", "message": f"{pl.sku}: {decimal_str(qty)} is more than can still be shipped ({decimal_str(room[pl.id])} of {decimal_str(pl.quantity)} ordered, after what is received or already on the road)"})
        out.append((pl.id, l.quantity))
    if errors:
        raise rule_violation(f"The dispatch has {len(errors)} problem{'s' if len(errors) > 1 else ''}: {'; '.join(e['message'] for e in errors)}", code="DISPATCH_VALIDATION_FAILED", meta={"errors": errors})
    return out


_COLS = {
    "dispatchDate": "dispatch_date", "expectedArrival": "expected_arrival", "transporter": "transporter", "vehicleNo": "vehicle_no", "lrNo": "lr_no",
    "driverName": "driver_name", "driverPhone": "driver_phone", "packages": "packages", "grossWeightKg": "gross_weight_kg", "invoiceNo": "invoice_no",
    "invoiceDate": "invoice_date", "invoiceValue": "invoice_value", "packingListNo": "packing_list_no", "deliveryChallanNo": "delivery_challan_no",
    "deliveryChallanDate": "delivery_challan_date", "ewayBillNo": "eway_bill_no", "ewayBillValidUntil": "eway_bill_valid_until", "notes": "notes",
}


@router.post("/{id}/dispatches", status_code=201)
def create_dispatch(id: uuid_mod.UUID, body: DispatchBody, actor: Actor = Depends(require_permission("po:vendor"))):
    tenant_id = actor["tenant_id"]
    po = _po(actor, id)
    _require_live(po, "record a dispatch")
    data = _validate_fields(body, dispatch_date=body.dispatchDate)
    lines = _validate_lines(po, body.lines)
    n = PoDispatch.query.filter_by(po_id=po.id).count() + 1
    row = PoDispatch(tenant_id=tenant_id, po_id=po.id, number=f"{po.number}/S{n}", status="in_transit", recorded_by_name=_name(actor), **{col: data[k] for k, col in _COLS.items()})
    session.add(row)
    session.flush()
    for line_id, qty in lines:
        session.add(PoDispatchLine(tenant_id=tenant_id, dispatch_id=row.id, po_line_id=line_id, quantity=qty))
    session.flush()
    _audit(actor, "po.dispatch_recorded", po, dispatch=row.number, transporter=row.transporter, vehicleNo=row.vehicle_no, ewayBillNo=row.eway_bill_no, lines=len(lines))
    session.commit()
    return tracking(po) | {"created": row.number}


def _in_transit(actor: Actor, po: PurchaseOrder, dispatch_id, doing: str) -> PoDispatch:
    d = repo.require_dispatch(actor["tenant_id"], po.id, dispatch_id)
    if d.status != "in_transit":
        raise rule_violation(f"{d.number} is {d.status}, so you cannot {doing}", code="DISPATCH_INVALID_STATE")
    return d


@router.patch("/{id}/dispatches/{dispatch_id}")
def patch_dispatch(id: uuid_mod.UUID, dispatch_id: uuid_mod.UUID, body: DispatchPatch, actor: Actor = Depends(require_permission("po:vendor"))):
    po = _po(actor, id)
    d = _in_transit(actor, po, dispatch_id, "edit it")
    given = body.model_fields_set - {"lines"}
    merged = {k: (getattr(body, k) if k in given else _current(d, k)) for k in _COLS}
    data = _validate_fields(DispatchFields.model_validate(merged, strict=False), dispatch_date=merged["dispatchDate"])
    for k in given:
        setattr(d, _COLS[k], data[k])
    if body.lines is not None:
        lines = _validate_lines(po, body.lines, exclude=d.id)
        PoDispatchLine.query.filter_by(dispatch_id=d.id).delete(synchronize_session=False)
        session.flush()
        for line_id, qty in lines:
            session.add(PoDispatchLine(tenant_id=d.tenant_id, dispatch_id=d.id, po_line_id=line_id, quantity=qty))
    _audit(actor, "po.dispatch_updated", po, dispatch=d.number, changed=sorted(given) + (["lines"] if body.lines is not None else []))
    session.commit()
    return tracking(po)


def _current(d: PoDispatch, key: str):
    v = getattr(d, _COLS[key])
    return decimal_str(v) if key in ("grossWeightKg", "invoiceValue") and v is not None else v


@router.post("/{id}/dispatches/{dispatch_id}/deliver")
def deliver_dispatch(id: uuid_mod.UUID, dispatch_id: uuid_mod.UUID, body: NoteBody, actor: Actor = Depends(require_permission("po:vendor"))):
    po = _po(actor, id)
    d = _in_transit(actor, po, dispatch_id, "mark it delivered")
    d.status, d.auto_delivered, d.delivered_at = "delivered", False, datetime.now(timezone.utc)
    if _clean(body.notes):
        d.notes = f"{d.notes}\nArrival: {_clean(body.notes)}" if d.notes else f"Arrival: {_clean(body.notes)}"
    _audit(actor, "po.dispatch_delivered", po, dispatch=d.number)
    session.commit()
    return tracking(po)


@router.post("/{id}/dispatches/{dispatch_id}/cancel")
def cancel_dispatch(id: uuid_mod.UUID, dispatch_id: uuid_mod.UUID, body: ReasonBody, actor: Actor = Depends(require_permission("po:vendor"))):
    po = _po(actor, id)
    d = _in_transit(actor, po, dispatch_id, "cancel it")
    d.status, d.cancelled_reason = "cancelled", body.reason.strip()
    _audit(actor, "po.dispatch_cancelled", po, reason=d.cancelled_reason, dispatch=d.number)
    session.commit()
    return tracking(po)
