"""GRN receiving: list/get/create/edit, inspect/qc/post/reject/cancel,
putaway, inventory items, rejection codes. Ported 1:1 (behavior) from
backend_py/app/routes/grns.py.

The QR/sticker endpoints (`GET /inventory-items/{id}/qr`, `POST
/inventory-items/decode-qr`, `POST /inventory-items/{id}/vendor-qr`, `GET
/grns/{id}/qr-codes`, `GET /grns/{id}/qr-codes/pdf`) live in qr_router.py -
they need Pillow/qrcode/zxing-cpp; the text-only hardware-scanner path
(`POST /inventory-items/resolve-scan`) stays here.
"""

from __future__ import annotations

import csv
import io
import re
import uuid as uuid_mod
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import func, or_

from app.core.auth import Actor, require_any_permission, require_permission
from app.core.access_scope import assert_warehouse_in_scope, scope_query_by_warehouse
from app.core.audit import audit, read_audit_trail
from app.core.config import settings
from app.core.db import session
from app.core.errors import ProblemError, conflict, not_found, rule_violation
from app.core.idempotency import get_raw_body, run_idempotent
from app.core.money import decimal_str, div, is_positive, is_zero, mul, round_dp, to_decimal
from app.core.pagination import ListQuery, list_response, offset_of, parse_sort
from app.domains.grn.schemas import (
    CancelBody,
    DisposeInventoryItemBody,
    GrnBody,
    GrnBulkUploadBody,
    GrnEditBody,
    GrnLineEditBody,
    InspectBody,
    LineBody,
    PutawayBody,
    QcBody,
    QcBulkUploadBody,
    QcLineDecision,
    RejectBody,
    RejectionCodeBody,
    ResolveInventoryScanBody,
)
from app.models.grn import Grn
from app.models.grn_line import GrnLine
from app.models.inventory_item import InventoryItem
from app.models.location import Location
from app.models.po_line import PoLine
from app.models.purchase_order import PurchaseOrder
from app.models.putaway_task import PutawayTask
from app.models.rejection_code import RejectionCode
from app.models.sticker_size import StickerSize
from app.models.stock_ledger import StockLedger
from app.services import grn_repo, inventory_ledger, product_repo, warehouse_repo
from app.services.grn_post import post_grn_tx
from app.services.grn_receiving import LocationRules, PoLineSnapshot, ProductRules, ReceiptLineInput, assert_receipt_valid, quality_status_for, receipt_line_problems
from app.services.grn_state import assert_editable, assert_transition
from app.services.inventory_ledger import LedgerPosting
from app.services.procurement_repo import get_receivable_po, reverse_grn_receipt
from app.services.sequences import next_document_number

router = APIRouter(prefix="/api/v1", tags=["grn"])

_WHOLE_RE = re.compile(r"^\d+(\.0+)?$")
SERIAL_UOMS = {"UNIT"}
_INVENTORY_ITEM_QR_RE = re.compile(r"/inventory-item/([0-9a-fA-F-]{36})")


def _is_serial_uom(uom: str) -> bool:
    return uom.upper() in SERIAL_UOMS


def _product_rules(summary: dict) -> ProductRules:
    return ProductRules(product_id=summary["id"], sku=summary["sku"], status=summary["status"], batch_tracked=summary["batchTracked"], expiry_tracked=summary["expiryTracked"], type=summary["type"], uom=summary["uom"])


def _location_rules_from_row(row) -> LocationRules:
    return LocationRules(id=str(row.id), code=row.code, warehouse_id=str(row.warehouse_id), status=row.status, type=row.type, allowed_product_types=row.allowed_product_types or [])


def _create_inventory_for_line(
    tenant_id,
    grn: Grn,
    grn_line: GrnLine,
    *,
    po_id,
    po_number: str,
    product_id,
    sku: str,
    warehouse_id,
    uom: str,
    serialized: bool,
    qty,
    batch_no: str | None,
    received_date,
) -> None:
    """Creates the piece/lot InventoryItem row(s) backing a freshly (re)received line quantity."""
    if serialized:
        inventory_ids = grn_repo.reserve_inventory_ids(tenant_id, int(to_decimal(qty)))
        for inv_id in inventory_ids:
            session.add(
                InventoryItem(
                    tenant_id=tenant_id,
                    inventory_id=inv_id,
                    grn_id=grn.id,
                    grn_line_id=grn_line.id,
                    po_id=po_id,
                    po_number=po_number,
                    product_id=product_id,
                    sku=sku,
                    warehouse_id=warehouse_id,
                    status="under_qc",
                    kind="piece",
                    quantity=1,
                    uom=uom,
                    received_date=received_date,
                    batch_no=batch_no,
                    vendor_qr_enabled=grn.has_vendor_qr,
                )
            )
    else:
        inv_id = grn_repo.reserve_inventory_ids(tenant_id, 1)[0]
        session.add(
            InventoryItem(
                tenant_id=tenant_id,
                inventory_id=inv_id,
                grn_id=grn.id,
                grn_line_id=grn_line.id,
                po_id=po_id,
                po_number=po_number,
                product_id=product_id,
                sku=sku,
                warehouse_id=warehouse_id,
                status="under_qc",
                kind="lot",
                quantity=qty,
                uom=uom,
                received_date=received_date,
                batch_no=batch_no,
                vendor_qr_enabled=grn.has_vendor_qr,
            )
        )


def _reconcile_inventory_for_qty_change(tenant_id, grn: Grn, grn_line: GrnLine, serialized: bool, new_qty, batch_no: str | None, received_date) -> None:
    """A pre-post edit changed a line's received quantity - undoes any QC
    decisions already recorded against its inventory and adds/soft-deletes
    piece rows, or resizes the single lot row, to match."""
    active_items = InventoryItem.query.filter_by(grn_line_id=grn_line.id, deleted_at=None).order_by(InventoryItem.inventory_id).all()
    for item in active_items:
        item.status = "under_qc"
        item.accepted_qty = 0
        item.rejected_qty = 0
        item.qc_by = None
        item.qc_at = None
        item.rejection_code = None
        item.rejection_note = None
        item.batch_no = batch_no

    new_q = to_decimal(new_qty)
    if serialized:
        diff = int(new_q) - len(active_items)
        if diff > 0:
            _create_inventory_for_line(
                tenant_id, grn, grn_line,
                po_id=grn.po_id, po_number=grn.po_number, product_id=grn_line.product_id, sku=grn_line.sku,
                warehouse_id=grn.warehouse_id, uom=grn_line.uom, serialized=True, qty=str(diff), batch_no=batch_no, received_date=received_date,
            )
        elif diff < 0:
            now = datetime.now(timezone.utc)
            for item in active_items[:(-diff)]:
                item.deleted_at = now
    elif active_items:
        active_items[0].quantity = new_q
    else:
        _create_inventory_for_line(
            tenant_id, grn, grn_line,
            po_id=grn.po_id, po_number=grn.po_number, product_id=grn_line.product_id, sku=grn_line.sku,
            warehouse_id=grn.warehouse_id, uom=grn_line.uom, serialized=False, qty=new_qty, batch_no=batch_no, received_date=received_date,
        )


#  GRN & QC's own nav/page permission is warehouse:read - a warehouse:read-only
#  role can already reach this whole page, so its own primary endpoints must
#  accept warehouse:read too.
_GRN_LOOKUP_PERMISSIONS = ("grn:read", "warehouse:read")


@router.get("/grns")
def list_grns(
    actor: Actor = Depends(require_any_permission(*_GRN_LOOKUP_PERMISSIONS)),
    query: ListQuery = Depends(),
    status: str | None = None,
    poId: uuid_mod.UUID | None = None,
    warehouseId: uuid_mod.UUID | None = None,
    vendorId: uuid_mod.UUID | None = None,
):
    tenant_id = actor["tenant_id"]

    q = Grn.query.filter(Grn.tenant_id == tenant_id)
    if status:
        statuses = [s.strip() for s in status.split(",") if s.strip()]
        if statuses:
            q = q.filter(Grn.status.in_(statuses))
    if poId:
        q = q.filter(Grn.po_id == poId)
    if warehouseId:
        assert_warehouse_in_scope(actor, warehouseId)
        q = q.filter(Grn.warehouse_id == warehouseId)
    else:
        q = scope_query_by_warehouse(q, Grn.warehouse_id, actor)
    if vendorId:
        q = q.filter(Grn.vendor_id == vendorId)
    if query.q:
        like = f"%{query.q}%"
        q = q.filter(or_(Grn.number.ilike(like), Grn.po_number.ilike(like), Grn.vendor_name.ilike(like)))

    total = q.count()
    order = parse_sort(query.sort, ["number", "received_date", "status", "created_at"], ("received_date", "desc"))
    for col, direction in order:
        column = getattr(Grn, col)
        q = q.order_by(column.desc() if direction == "desc" else column.asc())
    rows = q.limit(query.limit).offset(offset_of(query)).all()

    value_by_grn = grn_repo.received_goods_values([r.id for r in rows])
    name_by_warehouse = grn_repo.warehouse_names([r.warehouse_id for r in rows])
    return list_response(
        [
            grn_repo.to_grn_api(
                r,
                received_goods_value=value_by_grn.get(str(r.id), "0.00"),
                warehouse_name=name_by_warehouse.get(str(r.warehouse_id), r.warehouse_code),
            )
            for r in rows
        ],
        query,
        total,
    )


@router.get("/grns/{id}")
def get_grn(id: uuid_mod.UUID, actor: Actor = Depends(require_any_permission(*_GRN_LOOKUP_PERMISSIONS))):
    grn = grn_repo.require_grn(actor["tenant_id"], id)
    assert_warehouse_in_scope(actor, grn.warehouse_id)
    return grn_repo.to_grn_api(grn, grn_repo.grn_lines(id))


def _create_grn(tenant_id, actor: Actor, body: GrnBody) -> Grn:
    """Shared by the single-GRN create route and the bulk-upload route."""
    po = get_receivable_po(tenant_id, body.poId)
    if not po:
        raise not_found("Purchase order")
    if not po["receivable"]:
        raise rule_violation(f"{po['number']} is {po['status'].replace('_', ' ')} — goods can only be received against an issued purchase order", code="PO_NOT_RECEIVABLE")

    warehouse_id = body.warehouseId or uuid_mod.UUID(po["warehouseId"])
    warehouse = warehouse_repo.require_warehouse(tenant_id, warehouse_id)
    assert_warehouse_in_scope(actor, warehouse.id)
    if warehouse.status == "inactive":
        raise rule_violation(f"Warehouse {warehouse.code} is inactive", code="WAREHOUSE_INACTIVE")

    po_lines = {l["id"]: l for l in po["lines"]}
    product_ids = {l["productId"] for l in po["lines"]}
    products = product_repo.get_summaries(tenant_id, [uuid_mod.UUID(pid) for pid in product_ids])
    location_ids = {str(l.locationId) for l in body.lines if l.locationId}
    locations = {lid: loc for lid in location_ids if (loc := warehouse_repo.find_location(tenant_id, uuid_mod.UUID(lid))) is not None}

    errors: list[dict] = []
    resolved = []
    for i, line in enumerate(body.lines):
        po_line = po_lines.get(str(line.poLineId))
        product = products.get(po_line["productId"]) if po_line else None
        errors.extend(
            receipt_line_problems(
                ReceiptLineInput(
                    po_line_id=str(line.poLineId),
                    received_qty=line.receivedQty,
                    accepted_qty="0",
                    rejected_qty="0",
                    batch_no=line.batchNo,
                    expiry_date=line.expiryDate.isoformat() if line.expiryDate else None,
                    location_id=str(line.locationId) if line.locationId else None,
                    rejection_code=None,
                ),
                i,
                PoLineSnapshot(id=po_line["id"], product_id=po_line["productId"], sku=po_line["sku"], uom=po_line["uom"], ordered_qty=po_line["orderedQty"], received_qty=po_line["receivedQty"], rejected_qty=po_line["rejectedQty"], open_qty=po_line["openQty"], unit_price=po_line["unitPrice"]) if po_line else None,
                _product_rules(product) if product else None,
                _location_rules_from_row(locations[str(line.locationId)]) if line.locationId and str(line.locationId) in locations else None,
                tolerance_percent=po["tolerancePercent"],
                warehouse_id=str(warehouse.id),
                warehouse_allowed_types=warehouse.allowed_product_types or [],
            )
        )
        serialized = _is_serial_uom(product["uom"]) if product else False
        if serialized and not _WHOLE_RE.match(line.receivedQty):
            errors.append({"field": f"lines.{i}.receivedQty", "message": f"{po_line['sku'] if po_line else 'This item'} is counted in whole units — receive a whole number of pieces"})
        resolved.append({"line": line, "poLine": po_line, "product": product, "serialized": serialized})

    assert_receipt_valid(errors, f"Goods receipt against {po['number']}")

    invoice_clash = Grn.query.filter_by(tenant_id=tenant_id, vendor_id=po["vendorId"], invoice_number=body.invoiceNumber).first()
    if invoice_clash:
        raise conflict(f"Invoice {body.invoiceNumber} has already been recorded on GRN {invoice_clash.number} for this vendor", code="DUPLICATE_GRN_INVOICE_NUMBER")

    sticker_size = None
    if body.stickerSizeId:
        sticker_size = StickerSize.query.filter_by(tenant_id=tenant_id, id=body.stickerSizeId).first()
        if not sticker_size:
            raise not_found("Sticker size template")

    number = next_document_number(tenant_id, settings.grn_number_prefix, pad=4, start=8800)
    grn = Grn(
        tenant_id=tenant_id,
        number=number,
        po_id=body.poId,
        po_number=po["number"],
        vendor_id=po["vendorId"],
        vendor_name=po["vendorName"],
        warehouse_id=warehouse.id,
        warehouse_code=warehouse.code,
        status="under_qc",
        received_date=body.receivedDate or date.today(),
        vehicle_number=body.vehicleNumber,
        delivery_note=body.deliveryNote,
        gate_entry_no=body.gateEntryNo,
        invoice_number=body.invoiceNumber,
        notes=body.notes,
        sticker_size_id=sticker_size.id if sticker_size else None,
        sticker_size_name=sticker_size.name if sticker_size else None,
        has_vendor_qr=body.vendorQrEnabled,
        created_by=str(actor["user_id"]),
    )
    session.add(grn)
    session.flush()

    received_date = body.receivedDate or date.today()
    for i, r in enumerate(resolved):
        location = locations.get(str(r["line"].locationId)) if r["line"].locationId else None
        grn_line = GrnLine(
            tenant_id=tenant_id,
            grn_id=grn.id,
            line_no=i + 1,
            po_line_id=r["line"].poLineId,
            product_id=r["poLine"]["productId"],
            sku=r["poLine"]["sku"],
            ordered_qty=r["poLine"]["orderedQty"],
            received_qty=r["line"].receivedQty,
            accepted_qty=0,
            rejected_qty=0,
            uom=r["poLine"]["uom"],
            batch_no=r["line"].batchNo,
            expiry_date=r["line"].expiryDate,
            manufacture_date=r["line"].manufactureDate,
            location_id=r["line"].locationId,
            location_code=location.code if location else None,
            quality_status="pending",
            unit_price=r["poLine"]["unitPrice"],
        )
        session.add(grn_line)
        session.flush()

        _create_inventory_for_line(
            tenant_id, grn, grn_line,
            po_id=body.poId, po_number=po["number"], product_id=r["poLine"]["productId"], sku=r["poLine"]["sku"],
            warehouse_id=warehouse.id, uom=r["poLine"]["uom"], serialized=r["serialized"], qty=r["line"].receivedQty,
            batch_no=r["line"].batchNo, received_date=received_date,
        )

    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="grn.created", entity_type="grn", entity_id=str(grn.id), meta={"number": number, "po": po["number"], "lines": len(body.lines)})
    session.commit()
    return grn


@router.post("/grns", status_code=201)
def create_grn(body: GrnBody, request: Request, raw_body: bytes = Depends(get_raw_body), actor: Actor = Depends(require_permission("grn:write"))):
    tenant_id = actor["tenant_id"]

    def _do():
        grn = _create_grn(tenant_id, actor, body)
        return 201, grn_repo.to_grn_api(grn_repo.require_grn(tenant_id, grn.id), grn_repo.grn_lines(grn.id))

    status_code, response_body = run_idempotent(request.headers.get("Idempotency-Key"), "POST", request.url.path, raw_body, actor, _do)
    return JSONResponse(status_code=status_code, content=response_body)


def _parse_bool(value: str, default: bool) -> bool:
    v = (value or "").strip().lower()
    if v in ("true", "1", "yes", "y"):
        return True
    if v in ("false", "0", "no", "n"):
        return False
    return default


BULK_UPLOAD_REQUIRED_COLUMNS = ["grnRef", "poNumber", "invoiceNumber", "lineSku", "receivedQty"]


@router.post("/grns/bulk-upload")
def bulk_upload_grns(body: GrnBulkUploadBody, actor: Actor = Depends(require_permission("grn:write"))):
    """Creates many GRNs from one CSV in a single request. Each grnRef group
    is independent - one bad group is reported as an error and skipped."""
    tenant_id = actor["tenant_id"]

    reader = csv.DictReader(io.StringIO(body.csvContent))
    fieldnames = [(f or "").strip() for f in (reader.fieldnames or [])]
    missing_columns = [c for c in BULK_UPLOAD_REQUIRED_COLUMNS if c not in fieldnames]
    if missing_columns:
        raise rule_violation(f"CSV is missing required column(s): {', '.join(missing_columns)}", code="BULK_CSV_INVALID_HEADERS")

    groups: dict[str, list[dict]] = {}
    order: list[str] = []
    for row_number, raw_row in enumerate(reader, start=2):
        row = {(k or "").strip(): (v or "").strip() for k, v in raw_row.items() if k}
        row["_rowNumber"] = row_number
        ref = row.get("grnRef") or ""
        if not ref:
            continue
        if ref not in groups:
            groups[ref] = []
            order.append(ref)
        groups[ref].append(row)

    results = []
    for grn_ref in order:
        rows = groups[grn_ref]
        first = rows[0]
        errors: list[str] = []

        po_number = first.get("poNumber") or ""
        po_row = PurchaseOrder.query.filter_by(tenant_id=tenant_id, number=po_number).first() if po_number else None
        if not po_number:
            errors.append("poNumber is required")
        elif not po_row:
            errors.append(f"PO number '{po_number}' not found")

        received_date = None
        if first.get("receivedDate"):
            try:
                received_date = date.fromisoformat(first["receivedDate"])
            except ValueError:
                errors.append(f"Invalid receivedDate '{first['receivedDate']}' — use YYYY-MM-DD")

        sticker_size = None
        sticker_size_name = first.get("stickerSizeName") or ""
        if sticker_size_name:
            sticker_size = StickerSize.query.filter_by(tenant_id=tenant_id, name=sticker_size_name).first()
            if not sticker_size:
                errors.append(f"Sticker size template '{sticker_size_name}' not found")

        po: dict | None = None
        po_lines_by_sku: dict[str, dict] = {}
        if po_row:
            po = get_receivable_po(tenant_id, po_row.id)
            if not po:
                errors.append(f"PO '{po_number}' not found")
            elif not po["receivable"]:
                errors.append(f"{po['number']} is {po['status'].replace('_', ' ')} — goods can only be received against an issued purchase order")
            else:
                po_lines_by_sku = {l["sku"]: l for l in po["lines"]}

        lines: list[LineBody] = []
        for r in rows:
            row_no = r["_rowNumber"]
            sku = r.get("lineSku") or ""
            if not sku:
                errors.append(f"Row {row_no}: lineSku is required")
                continue
            po_line = po_lines_by_sku.get(sku)
            if po_row and po and not po_line:
                errors.append(f"Row {row_no}: PO {po_number} has no line for SKU '{sku}'")
                continue
            received_qty = r.get("receivedQty") or ""
            if not received_qty:
                errors.append(f"Row {row_no}: receivedQty is required")
                continue
            if not po_line:
                continue

            location_id = None
            location_code = r.get("locationCode") or ""
            if location_code:
                location_row = Location.query.filter(Location.warehouse_id == uuid_mod.UUID(po["warehouseId"]), func.upper(Location.code) == location_code.upper()).first()
                if not location_row:
                    errors.append(f"Row {row_no}: location code '{location_code}' not found in warehouse {po['warehouseCode']}")
                    continue
                location_id = location_row.id

            try:
                lines.append(
                    LineBody(
                        poLineId=uuid_mod.UUID(po_line["id"]),
                        receivedQty=received_qty,
                        batchNo=r.get("batchNo") or None,
                        expiryDate=date.fromisoformat(r["expiryDate"]) if r.get("expiryDate") else None,
                        manufactureDate=date.fromisoformat(r["manufactureDate"]) if r.get("manufactureDate") else None,
                        locationId=location_id,
                    )
                )
            except (ValidationError, ValueError) as exc:
                message = exc.errors()[0].get("msg", "invalid line data") if isinstance(exc, ValidationError) else str(exc)
                errors.append(f"Row {row_no}: {message}")

        if not errors and not lines:
            errors.append("No line items")

        if errors:
            results.append({"grnRef": grn_ref, "status": "error", "error": "; ".join(errors), "rows": rows})
            continue

        try:
            grn_body = GrnBody(
                poId=po_row.id,
                receivedDate=received_date,
                vehicleNumber=first.get("vehicleNumber") or None,
                deliveryNote=first.get("deliveryNote") or None,
                gateEntryNo=first.get("gateEntryNo") or None,
                invoiceNumber=first.get("invoiceNumber") or None,
                notes=first.get("notes") or None,
                stickerSizeId=sticker_size.id if sticker_size else None,
                vendorQrEnabled=_parse_bool(first.get("vendorQrEnabled", ""), False),
                lines=lines,
            )
        except ValidationError as exc:
            results.append({"grnRef": grn_ref, "status": "error", "error": exc.errors()[0].get("msg", "invalid GRN data"), "rows": rows})
            continue

        try:
            grn = _create_grn(tenant_id, actor, grn_body)
            results.append({"grnRef": grn_ref, "status": "success", "grnNumber": grn.number, "rows": rows})
        except ProblemError as exc:
            session.rollback()
            results.append({"grnRef": grn_ref, "status": "error", "error": exc.detail, "rows": rows})
        except Exception as exc:  # noqa: BLE001 - one bad group must not fail the whole batch
            session.rollback()
            results.append({"grnRef": grn_ref, "status": "error", "error": str(exc), "rows": rows})

    success_count = sum(1 for r in results if r["status"] == "success")
    error_count = len(results) - success_count
    return {
        "summary": {"totalGroups": len(results), "successCount": success_count, "errorCount": error_count},
        "results": [
            {
                "grnRef": r["grnRef"],
                "status": r["status"],
                "grnNumber": r.get("grnNumber"),
                "error": r.get("error"),
                "rows": [{k: v for k, v in row.items() if k != "_rowNumber"} for row in r["rows"]] if r["status"] == "error" else [],
            }
            for r in results
        ],
    }


@router.patch("/grns/{id}")
def update_grn(id: uuid_mod.UUID, body: GrnEditBody, actor: Actor = Depends(require_permission("grn:write"))):
    """Edits a not-yet-posted GRN: warehouse, line quantities/batches, and
    adding or removing SKU lines. Sends the *complete* desired line set; any
    existing line missing from it is treated as removed."""
    tenant_id = actor["tenant_id"]
    grn = grn_repo.require_grn(tenant_id, id)
    assert_warehouse_in_scope(actor, grn.warehouse_id)
    assert_editable(grn.number, grn.status)

    po = get_receivable_po(tenant_id, grn.po_id)
    if not po:
        raise not_found("Purchase order")

    if body.warehouseId and body.warehouseId != grn.warehouse_id:
        assert_warehouse_in_scope(actor, body.warehouseId)
        warehouse = warehouse_repo.require_warehouse(tenant_id, body.warehouseId)
        if warehouse.status == "inactive":
            raise rule_violation(f"Warehouse {warehouse.code} is inactive", code="WAREHOUSE_INACTIVE")
        grn.warehouse_id = warehouse.id
        grn.warehouse_code = warehouse.code
        InventoryItem.query.filter_by(grn_id=grn.id, deleted_at=None).update({"warehouse_id": warehouse.id}, synchronize_session=False)
    else:
        warehouse = warehouse_repo.require_warehouse(tenant_id, grn.warehouse_id)

    po_lines = {l["id"]: l for l in po["lines"]}
    product_ids = {l["productId"] for l in po["lines"]}
    products = product_repo.get_summaries(tenant_id, [uuid_mod.UUID(pid) for pid in product_ids])
    location_ids = {str(l.locationId) for l in body.lines if l.locationId}
    locations = {lid: loc for lid in location_ids if (loc := warehouse_repo.find_location(tenant_id, uuid_mod.UUID(lid))) is not None}
    existing_lines = {str(l.id): l for l in grn_repo.grn_lines(id)}

    errors: list[dict] = []
    resolved = []
    for i, line in enumerate(body.lines):
        po_line = po_lines.get(str(line.poLineId))
        product = products.get(po_line["productId"]) if po_line else None
        existing = existing_lines.get(str(line.id)) if line.id else None
        errors.extend(
            receipt_line_problems(
                ReceiptLineInput(
                    po_line_id=str(line.poLineId),
                    received_qty=line.receivedQty,
                    accepted_qty="0",
                    rejected_qty="0",
                    batch_no=line.batchNo,
                    expiry_date=line.expiryDate.isoformat() if line.expiryDate else None,
                    location_id=str(line.locationId) if line.locationId else None,
                    rejection_code=None,
                ),
                i,
                PoLineSnapshot(id=po_line["id"], product_id=po_line["productId"], sku=po_line["sku"], uom=po_line["uom"], ordered_qty=po_line["orderedQty"], received_qty=po_line["receivedQty"], rejected_qty=po_line["rejectedQty"], open_qty=po_line["openQty"], unit_price=po_line["unitPrice"]) if po_line else None,
                _product_rules(product) if product else None,
                _location_rules_from_row(locations[str(line.locationId)]) if line.locationId and str(line.locationId) in locations else None,
                tolerance_percent=po["tolerancePercent"],
                warehouse_id=str(warehouse.id),
                warehouse_allowed_types=warehouse.allowed_product_types or [],
            )
        )
        serialized = _is_serial_uom(product["uom"]) if product else False
        if serialized and not _WHOLE_RE.match(line.receivedQty):
            errors.append({"field": f"lines.{i}.receivedQty", "message": f"{po_line['sku'] if po_line else 'This item'} is counted in whole units — receive a whole number of pieces"})
        resolved.append({"line": line, "poLine": po_line, "product": product, "serialized": serialized, "existing": existing})

    assert_receipt_valid(errors, f"{grn.number} edit")

    received_date = grn.received_date
    next_line_no = max((l.line_no for l in existing_lines.values()), default=0) + 1
    kept_ids: set[str] = set()
    for r in resolved:
        line = r["line"]
        po_line = r["poLine"]
        location = locations.get(str(line.locationId)) if line.locationId else None
        if r["existing"]:
            grn_line = r["existing"]
            kept_ids.add(str(grn_line.id))
            qty_changed = to_decimal(grn_line.received_qty) != to_decimal(line.receivedQty)
            grn_line.received_qty = line.receivedQty
            grn_line.batch_no = line.batchNo
            grn_line.expiry_date = line.expiryDate
            grn_line.manufacture_date = line.manufactureDate
            if line.locationId:
                grn_line.location_id = line.locationId
                grn_line.location_code = location.code if location else grn_line.location_code
            if qty_changed:
                grn_line.accepted_qty = 0
                grn_line.rejected_qty = 0
                grn_line.quality_status = "pending"
                grn_line.rejection_code = None
                grn_line.rejection_note = None
                _reconcile_inventory_for_qty_change(tenant_id, grn, grn_line, r["serialized"], line.receivedQty, line.batchNo, received_date)
            else:
                InventoryItem.query.filter_by(grn_line_id=grn_line.id, deleted_at=None).update({"batch_no": line.batchNo}, synchronize_session=False)
        else:
            grn_line = GrnLine(
                tenant_id=tenant_id,
                grn_id=grn.id,
                line_no=next_line_no,
                po_line_id=line.poLineId,
                product_id=po_line["productId"],
                sku=po_line["sku"],
                ordered_qty=po_line["orderedQty"],
                received_qty=line.receivedQty,
                accepted_qty=0,
                rejected_qty=0,
                uom=po_line["uom"],
                batch_no=line.batchNo,
                expiry_date=line.expiryDate,
                manufacture_date=line.manufactureDate,
                location_id=line.locationId,
                location_code=location.code if location else None,
                quality_status="pending",
                unit_price=po_line["unitPrice"],
            )
            next_line_no += 1
            session.add(grn_line)
            session.flush()
            kept_ids.add(str(grn_line.id))
            _create_inventory_for_line(
                tenant_id, grn, grn_line,
                po_id=grn.po_id, po_number=po["number"], product_id=po_line["productId"], sku=po_line["sku"],
                warehouse_id=warehouse.id, uom=po_line["uom"], serialized=r["serialized"], qty=line.receivedQty,
                batch_no=line.batchNo, received_date=received_date,
            )

    now = datetime.now(timezone.utc)
    for lid, grn_line in existing_lines.items():
        if lid not in kept_ids:
            grn_line.deleted_at = now
            InventoryItem.query.filter_by(grn_line_id=grn_line.id, deleted_at=None).update({"deleted_at": now}, synchronize_session=False)

    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="grn.edited", entity_type="grn", entity_id=str(id), meta={"lines": len(body.lines)})
    session.commit()
    return grn_repo.to_grn_api(grn_repo.require_grn(tenant_id, id), grn_repo.grn_lines(id))


@router.patch("/grns/{id}/inspect")
def inspect_grn(id: uuid_mod.UUID, body: InspectBody, actor: Actor = Depends(require_permission("grn:write"))):
    tenant_id = actor["tenant_id"]
    grn = grn_repo.require_grn(tenant_id, id)
    assert_warehouse_in_scope(actor, grn.warehouse_id)
    assert_editable(grn.number, grn.status)
    lines = {str(l.id): l for l in grn_repo.grn_lines(id)}

    errors: list[dict] = []
    for i, incoming in enumerate(body.lines):
        line = lines.get(str(incoming.lineId))
        if not line:
            errors.append({"field": f"lines.{i}", "message": f"Line {incoming.lineId} is not on {grn.number}"})
            continue
        total = to_decimal(incoming.acceptedQty) + to_decimal(incoming.rejectedQty)
        if total > to_decimal(line.received_qty):
            errors.append({"field": f"lines.{i}", "message": f"{line.sku}: accepted + rejected ({decimal_str(total)}) exceeds the received quantity ({decimal_str(line.received_qty)})"})
        if is_positive(incoming.rejectedQty) and not incoming.rejectionCode:
            errors.append({"field": f"lines.{i}.rejectionCode", "message": f"{line.sku}: a rejection reason code is required"})
    assert_receipt_valid(errors, grn.number)

    for incoming in body.lines:
        line = lines[str(incoming.lineId)]
        line.accepted_qty = incoming.acceptedQty
        line.rejected_qty = incoming.rejectedQty
        line.quality_status = quality_status_for(incoming.acceptedQty, incoming.rejectedQty, line.received_qty)
        line.rejection_code = incoming.rejectionCode
        line.rejection_note = incoming.rejectionNote
        if incoming.locationId:
            line.location_id = incoming.locationId

    grn.status = "under_qc"
    grn.inspected_by = str(actor["user_id"])
    grn.inspected_at = datetime.now(timezone.utc)
    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="grn.inspected", entity_type="grn", entity_id=str(id), meta={"lines": len(body.lines)})
    session.commit()

    return grn_repo.to_grn_api(grn_repo.require_grn(tenant_id, id), grn_repo.grn_lines(id))


@router.post("/grns/{id}/post")
def post_grn(id: uuid_mod.UUID, actor: Actor = Depends(require_permission("grn:post"))):
    tenant_id = actor["tenant_id"]
    grn = grn_repo.require_grn(tenant_id, id)
    assert_warehouse_in_scope(actor, grn.warehouse_id)
    assert_transition(grn.number, grn.status, "posted")

    lines = grn_repo.grn_lines(id)
    pending = [l for l in lines if l.quality_status == "pending"]
    if pending:
        raise rule_violation(f"{grn.number} still has {len(pending)} line(s) awaiting QC ({', '.join(l.sku for l in pending)}) — complete QC testing before posting", code="GRN_INSPECTION_INCOMPLETE")

    post_grn_tx(tenant_id, grn, lines, str(actor["user_id"]))
    session.commit()

    return grn_repo.to_grn_api(grn_repo.require_grn(tenant_id, id), grn_repo.grn_lines(id))


@router.get("/grns/{id}/items")
def get_grn_items(id: uuid_mod.UUID, actor: Actor = Depends(require_any_permission(*_GRN_LOOKUP_PERMISSIONS))):
    tenant_id = actor["tenant_id"]
    grn = grn_repo.require_grn(tenant_id, id)
    assert_warehouse_in_scope(actor, grn.warehouse_id)
    items = grn_repo.grn_items(id)
    products = product_repo.get_summaries(tenant_id, [i.product_id for i in items])
    data = []
    for i in items:
        row = grn_repo.to_inventory_item_api(i)
        product = products.get(str(i.product_id))
        row["productName"] = product["name"] if product else None
        row["productMake"] = product["make"] if product else None
        row["vendorName"] = grn.vendor_name
        data.append(row)
    return {"data": data}


@router.get("/inventory-items")
def list_inventory_items(
    actor: Actor = Depends(require_permission("inventory:read")),
    query: ListQuery = Depends(),
    status: str | None = None,
    available: bool = False,
    bucket: str | None = None,
    notFullyConsumed: bool = False,
    consumed: bool = False,
    fullyConsumed: bool = False,
    writtenOff: bool = False,
    inTransit: bool = False,
    hasAccepted: bool = False,
    hasRejected: bool = False,
    warehouseId: uuid_mod.UUID | None = None,
    locationId: uuid_mod.UUID | None = None,
    productId: uuid_mod.UUID | None = None,
    grnId: uuid_mod.UUID | None = None,
):
    tenant_id = actor["tenant_id"]

    q = InventoryItem.query.filter(InventoryItem.tenant_id == tenant_id, InventoryItem.deleted_at.is_(None))
    if status:
        q = q.filter(InventoryItem.status == status)
    if available:
        q = q.filter(
            InventoryItem.accepted_qty - InventoryItem.consumed_qty - InventoryItem.written_off_qty > 0,
            InventoryItem.transfer_id.is_(None),
            InventoryItem.bucket == "available",
        )
    if bucket:
        q = q.filter(InventoryItem.bucket == bucket)
    if notFullyConsumed:
        q = q.filter(InventoryItem.accepted_qty - InventoryItem.consumed_qty > 0)
    if consumed:
        q = q.filter(InventoryItem.consumed_qty > 0)
    if fullyConsumed:
        q = q.filter(InventoryItem.consumed_qty > 0, InventoryItem.consumed_qty >= InventoryItem.accepted_qty, InventoryItem.written_off_qty == 0)
    if writtenOff:
        q = q.filter(InventoryItem.written_off_qty > 0, InventoryItem.accepted_qty - InventoryItem.consumed_qty - InventoryItem.written_off_qty <= 0)
    if inTransit:
        q = q.filter(InventoryItem.transfer_id.isnot(None))
    if hasAccepted:
        q = q.filter(InventoryItem.accepted_qty > 0)
    if hasRejected:
        q = q.filter(InventoryItem.rejected_qty > 0)
    if warehouseId:
        assert_warehouse_in_scope(actor, warehouseId)
        q = q.filter(InventoryItem.warehouse_id == warehouseId)
    else:
        q = scope_query_by_warehouse(q, InventoryItem.warehouse_id, actor)
    if locationId:
        q = q.filter(InventoryItem.location_id == locationId)
    if productId:
        q = q.filter(InventoryItem.product_id == productId)
    if grnId:
        q = q.filter(InventoryItem.grn_id == grnId)
    if query.q:
        like = f"%{query.q}%"
        q = q.filter(or_(InventoryItem.inventory_id.ilike(like), InventoryItem.sku.ilike(like)))

    total = q.count()
    rows = q.order_by(InventoryItem.inventory_id).limit(query.limit).offset(offset_of(query)).all()
    return list_response([grn_repo.to_inventory_item_api(r) for r in rows], query, total)


def _require_inventory_item(tenant_id, id: uuid_mod.UUID) -> InventoryItem:
    item = InventoryItem.query.filter_by(tenant_id=tenant_id, id=id, deleted_at=None).first()
    if not item:
        raise not_found("Inventory item")
    return item


@router.post("/inventory-items/{id}/dispose")
def dispose_inventory_item(id: uuid_mod.UUID, body: DisposeInventoryItemBody, actor: Actor = Depends(require_permission("inventory:adjust"))):
    """Closes out a rejected item's story - Returned to Vendor or Discarded."""
    tenant_id = actor["tenant_id"]
    item = _require_inventory_item(tenant_id, id)
    assert_warehouse_in_scope(actor, item.warehouse_id)

    if item.status != "rejected":
        raise rule_violation(f"{item.inventory_id} is {item.status.replace('_', ' ')} — only a rejected item can be disposed of", code="ITEM_NOT_REJECTED")

    item.status = body.disposition
    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action=f"inventory-item.{body.disposition}", entity_type="inventory-item", entity_id=str(item.id), meta={"inventoryId": item.inventory_id})
    session.commit()
    return grn_repo.to_inventory_item_api(item)


@router.get("/inventory-items/{id}")
def get_inventory_item(id: uuid_mod.UUID, actor: Actor = Depends(require_permission("inventory:read"))):
    """The QR-code landing page's data source - one physical unit's full
    receiving/QC/location context."""
    tenant_id = actor["tenant_id"]
    item = _require_inventory_item(tenant_id, id)
    assert_warehouse_in_scope(actor, item.warehouse_id)
    result = grn_repo.to_inventory_item_api(item)
    warehouse = warehouse_repo.find_warehouse(tenant_id, item.warehouse_id)
    result["warehouseCode"] = warehouse.code if warehouse else None
    result["warehouseName"] = warehouse.name if warehouse else None
    grn = grn_repo.find_grn(tenant_id, item.grn_id)
    result["grnNumber"] = grn.number if grn else None
    result["vendorId"] = str(grn.vendor_id) if grn and grn.vendor_id else None
    result["vendorName"] = grn.vendor_name if grn else None

    product = product_repo.get_summary(tenant_id, item.product_id)
    result["productName"] = product["name"] if product else None
    result["productMake"] = product["make"] if product else None
    result["productCategory"] = product["categoryName"] if product else None
    result["productType"] = product["type"] if product else None

    grn_line = GrnLine.query.filter_by(tenant_id=tenant_id, id=item.grn_line_id).first()
    unit_price = grn_line.unit_price if grn_line else to_decimal(0)
    tax_rate = to_decimal(0)
    if grn_line and grn_line.po_line_id:
        po_line = PoLine.query.filter_by(tenant_id=tenant_id, id=grn_line.po_line_id).first()
        tax_rate = po_line.tax_rate if po_line else to_decimal(0)
    net_amount = round_dp(mul(item.quantity, unit_price), 2)
    tax_amount = round_dp(div(mul(net_amount, tax_rate), 100), 2)
    result["unitPrice"] = decimal_str(unit_price)
    result["taxRate"] = decimal_str(tax_rate)
    result["netAmount"] = decimal_str(net_amount)
    result["taxAmount"] = decimal_str(tax_amount)
    result["totalAmount"] = decimal_str(net_amount + tax_amount)
    return result


def _resolve_inventory_item_from_text(tenant_id, actor: Actor, text: str) -> InventoryItem:
    """Raw decoded/typed text -> the InventoryItem it points at. Either one
    of our own /inventory-item/{uuid} QR URLs, or - for "Scan to Jump" - the
    plain Inventory ID itself (e.g. "INV-108623"), matched exactly and
    case-insensitively."""
    match = _INVENTORY_ITEM_QR_RE.search(text)
    if match:
        try:
            item_id = uuid_mod.UUID(match.group(1))
        except ValueError:
            raise rule_violation("That QR code isn't a Simple ERP Inventory ID tag", code="QR_NOT_RECOGNIZED")
        item = _require_inventory_item(tenant_id, item_id)
    else:
        item = InventoryItem.query.filter(
            InventoryItem.tenant_id == tenant_id,
            InventoryItem.deleted_at.is_(None),
            InventoryItem.inventory_id.ilike(text.strip()),
        ).first()
        if not item:
            raise rule_violation("That doesn't match a Simple ERP Inventory ID or QR code", code="QR_NOT_RECOGNIZED")

    assert_warehouse_in_scope(actor, item.warehouse_id)
    return item


@router.post("/inventory-items/resolve-scan")
def resolve_inventory_item_scan(body: ResolveInventoryScanBody, actor: Actor = Depends(require_permission("inventory:read"))):
    """Text-only counterpart to the (deferred) photo-decode endpoint, for a
    hardware (HID keyboard-emulation) scanner: it types the QR's raw text
    plus a trailing Enter directly into whatever field/listener is focused."""
    tenant_id = actor["tenant_id"]
    item = _resolve_inventory_item_from_text(tenant_id, actor, body.text)
    return grn_repo.to_inventory_item_api(item)


def _qc_grn(tenant_id, actor: Actor, id: uuid_mod.UUID, body: QcBody) -> Grn:
    """Shared by the single-GRN QC route and the bulk-upload route."""
    if len(body.items) + len(body.lines) == 0:
        raise rule_violation("Record at least one QC decision", code="VALIDATION_FAILED")
    grn = grn_repo.require_grn(tenant_id, id)
    assert_warehouse_in_scope(actor, grn.warehouse_id)
    assert_editable(grn.number, grn.status)

    items = {str(it.id): it for it in grn_repo.grn_items(id)}
    lines = {str(l.id): l for l in grn_repo.grn_lines(id)}

    errors: list[dict] = []
    for i, d in enumerate(body.items):
        item = items.get(str(d.itemId))
        if not item:
            errors.append({"field": f"items.{i}", "message": f"Item {d.itemId} is not on {grn.number}"})
        elif d.decision == "reject" and not d.rejectionCode:
            errors.append({"field": f"items.{i}.rejectionCode", "message": f"{item.inventory_id}: a rejection reason code is required"})
    for i, d in enumerate(body.lines):
        line = lines.get(str(d.lineId))
        if not line:
            errors.append({"field": f"lines.{i}", "message": f"Line {d.lineId} is not on {grn.number}"})
            continue
        if any(it.grn_line_id == d.lineId and it.kind == "piece" for it in items.values()):
            errors.append({"field": f"lines.{i}", "message": f"{line.sku} is serialised — test it piece by piece, not by quantity"})
            continue
        total = to_decimal(d.acceptedQty) + to_decimal(d.rejectedQty)
        if total > to_decimal(line.received_qty):
            errors.append({"field": f"lines.{i}", "message": f"{line.sku}: accepted + rejected ({decimal_str(total)}) exceeds the received quantity ({decimal_str(line.received_qty)})"})
        if is_positive(d.rejectedQty) and not d.rejectionCode:
            errors.append({"field": f"lines.{i}.rejectionCode", "message": f"{line.sku}: a rejection reason code is required"})
    assert_receipt_valid(errors, grn.number)

    touched_serial_lines: set[uuid_mod.UUID] = set()
    for d in body.items:
        item = items[str(d.itemId)]
        touched_serial_lines.add(item.grn_line_id)
        accepted = d.decision == "accept"
        item.status = "accepted" if accepted else "rejected"
        item.accepted_qty = 1 if accepted else 0
        item.rejected_qty = 0 if accepted else 1
        item.qc_by = str(actor["user_id"])
        item.qc_at = datetime.now(timezone.utc)
        item.rejection_code = None if accepted else d.rejectionCode
        item.rejection_note = None if accepted else d.rejectionNote

    for line_id in touched_serial_lines:
        piece_items = [it for it in items.values() if it.grn_line_id == line_id]
        accepted_count = sum(1 for it in piece_items if it.status == "accepted")
        rejected_count = sum(1 for it in piece_items if it.status == "rejected")
        total_count = len(piece_items)
        if accepted_count + rejected_count == 0:
            quality = "pending"
        elif rejected_count == 0 and accepted_count >= total_count:
            quality = "passed"
        elif accepted_count == 0 and rejected_count >= total_count:
            quality = "failed"
        else:
            quality = "partial"
        line = lines[str(line_id)]
        line.accepted_qty = accepted_count
        line.rejected_qty = rejected_count
        line.quality_status = quality
        line.rejection_code = (line.rejection_code or "QC-FAIL") if rejected_count > 0 else None

    for d in body.lines:
        line = lines[str(d.lineId)]
        line.accepted_qty = d.acceptedQty
        line.rejected_qty = d.rejectedQty
        line.quality_status = quality_status_for(d.acceptedQty, d.rejectedQty, line.received_qty)
        line.rejection_code = d.rejectionCode
        line.rejection_note = d.rejectionNote

        acc = to_decimal(d.acceptedQty)
        rej = to_decimal(d.rejectedQty)
        lot_status = "partial" if is_positive(acc) and is_positive(rej) else "accepted" if is_positive(acc) else "rejected" if is_positive(rej) else "under_qc"
        lot_item = InventoryItem.query.filter_by(grn_line_id=d.lineId, grn_id=id, kind="lot", deleted_at=None).first()
        if lot_item:
            lot_item.accepted_qty = d.acceptedQty
            lot_item.rejected_qty = d.rejectedQty
            lot_item.status = lot_status
            lot_item.qc_by = str(actor["user_id"])
            lot_item.qc_at = datetime.now(timezone.utc)
            lot_item.rejection_code = (d.rejectionCode or "QC-FAIL") if is_positive(rej) else None
            lot_item.rejection_note = d.rejectionNote if is_positive(rej) else None

    grn.inspected_by = str(actor["user_id"])
    grn.inspected_at = datetime.now(timezone.utc)
    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="grn.qc", entity_type="grn", entity_id=str(id), meta={"items": len(body.items), "lines": len(body.lines)})

    # Post the moment QC is complete: every line fully resolved and no piece
    # still awaiting a verdict.
    session.flush()
    final_lines = grn_repo.grn_lines(id)
    all_resolved = len(final_lines) > 0 and all(not is_zero(l.received_qty) and is_zero(to_decimal(l.accepted_qty) + to_decimal(l.rejected_qty) - to_decimal(l.received_qty)) for l in final_lines)
    still_under_qc = InventoryItem.query.filter_by(grn_id=id, status="under_qc", deleted_at=None).count()
    if all_resolved and still_under_qc == 0:
        post_grn_tx(tenant_id, grn, final_lines, str(actor["user_id"]))

    session.commit()
    return grn


@router.post("/grns/{id}/qc")
def qc_grn(id: uuid_mod.UUID, body: QcBody, actor: Actor = Depends(require_permission("grn:write"))):
    tenant_id = actor["tenant_id"]
    grn = _qc_grn(tenant_id, actor, id, body)
    return grn_repo.to_grn_api(grn_repo.require_grn(tenant_id, grn.id), grn_repo.grn_lines(grn.id))


QC_BULK_UPLOAD_REQUIRED_COLUMNS = ["grnNumber", "lineSku", "acceptedQty"]


@router.post("/grns/qc/bulk-upload")
def bulk_upload_qc(body: QcBulkUploadBody, actor: Actor = Depends(require_permission("grn:write"))):
    """Records many GRNs' lot-line QC decisions from one CSV in a single
    request (lot-level only - piece-by-piece decisions on serialised items
    aren't a spreadsheet workflow)."""
    tenant_id = actor["tenant_id"]

    reader = csv.DictReader(io.StringIO(body.csvContent))
    fieldnames = [(f or "").strip() for f in (reader.fieldnames or [])]
    missing_columns = [c for c in QC_BULK_UPLOAD_REQUIRED_COLUMNS if c not in fieldnames]
    if missing_columns:
        raise rule_violation(f"CSV is missing required column(s): {', '.join(missing_columns)}", code="BULK_CSV_INVALID_HEADERS")

    groups: dict[str, list[dict]] = {}
    order: list[str] = []
    for row_number, raw_row in enumerate(reader, start=2):
        row = {(k or "").strip(): (v or "").strip() for k, v in raw_row.items() if k}
        row["_rowNumber"] = row_number
        ref = row.get("grnNumber") or ""
        if not ref:
            continue
        if ref not in groups:
            groups[ref] = []
            order.append(ref)
        groups[ref].append(row)

    results = []
    for grn_number in order:
        rows = groups[grn_number]
        errors: list[str] = []

        grn_row = Grn.query.filter_by(tenant_id=tenant_id, number=grn_number).first()
        if not grn_row:
            errors.append(f"GRN number '{grn_number}' not found")

        lines_by_sku: dict[str, object] = {}
        if grn_row:
            lines_by_sku = {l.sku: l for l in grn_repo.grn_lines(grn_row.id)}

        decisions: list[QcLineDecision] = []
        for r in rows:
            row_no = r["_rowNumber"]
            sku = r.get("lineSku") or ""
            if not sku:
                errors.append(f"Row {row_no}: lineSku is required")
                continue
            line = lines_by_sku.get(sku)
            if grn_row and not line:
                errors.append(f"Row {row_no}: GRN {grn_number} has no line for SKU '{sku}'")
                continue
            accepted_qty = r.get("acceptedQty") or ""
            if not accepted_qty:
                errors.append(f"Row {row_no}: acceptedQty is required")
                continue
            if not line:
                continue
            try:
                decisions.append(
                    QcLineDecision(
                        lineId=line.id,
                        acceptedQty=accepted_qty,
                        rejectedQty=r.get("rejectedQty") or "0",
                        rejectionCode=r.get("rejectionCode") or None,
                        rejectionNote=r.get("rejectionNote") or None,
                    )
                )
            except ValidationError as exc:
                errors.append(f"Row {row_no}: {exc.errors()[0].get('msg', 'invalid QC data')}")

        if not errors and not decisions:
            errors.append("No QC decisions")

        if errors:
            results.append({"grnNumber": grn_number, "status": "error", "error": "; ".join(errors), "rows": rows})
            continue

        try:
            qc_body = QcBody(items=[], lines=decisions)
        except ValidationError as exc:
            results.append({"grnNumber": grn_number, "status": "error", "error": exc.errors()[0].get("msg", "invalid QC data"), "rows": rows})
            continue

        try:
            grn = _qc_grn(tenant_id, actor, grn_row.id, qc_body)
            results.append({"grnNumber": grn_number, "status": "success", "grnStatus": grn.status, "rows": rows})
        except ProblemError as exc:
            session.rollback()
            results.append({"grnNumber": grn_number, "status": "error", "error": exc.detail, "rows": rows})
        except Exception as exc:  # noqa: BLE001 - one bad group must not fail the whole batch
            session.rollback()
            results.append({"grnNumber": grn_number, "status": "error", "error": str(exc), "rows": rows})

    success_count = sum(1 for r in results if r["status"] == "success")
    error_count = len(results) - success_count
    return {
        "summary": {"totalGroups": len(results), "successCount": success_count, "errorCount": error_count},
        "results": [
            {
                "grnNumber": r["grnNumber"],
                "status": r["status"],
                "grnStatus": r.get("grnStatus"),
                "error": r.get("error"),
                "rows": [{k: v for k, v in row.items() if k != "_rowNumber"} for row in r["rows"]] if r["status"] == "error" else [],
            }
            for r in results
        ],
    }


@router.post("/grns/{id}/reject")
def reject_grn(id: uuid_mod.UUID, body: RejectBody, actor: Actor = Depends(require_permission("grn:post"))):
    tenant_id = actor["tenant_id"]
    grn = grn_repo.require_grn(tenant_id, id)
    assert_warehouse_in_scope(actor, grn.warehouse_id)
    assert_transition(grn.number, grn.status, "rejected")

    grn.status = "rejected"
    grn.rejection_reason = body.reason
    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="grn.rejected", entity_type="grn", entity_id=str(id), reason=body.reason)
    session.commit()

    return grn_repo.to_grn_api(grn_repo.require_grn(tenant_id, id), grn_repo.grn_lines(id))


def _reverse_grn_ledger_entries(tenant_id, grn: Grn, actor_id: str, reason: str) -> None:
    """Reverses every receipt-side stock_ledger row this GRN posted (accepted
    -> available, rejected -> quarantine) with paired reversing entries."""
    receipt_rows = StockLedger.query.filter(
        StockLedger.tenant_id == tenant_id,
        StockLedger.reference_type.in_(["grn", "grn-rejected"]),
        StockLedger.reference_no == grn.number,
        StockLedger.movement_type == "receipt",
    ).all()
    if not receipt_rows:
        return
    already_reversed = {
        row.reverses_id
        for row in StockLedger.query.filter(
            StockLedger.tenant_id == tenant_id,
            StockLedger.movement_type == "reversal",
            StockLedger.reverses_id.in_([r.id for r in receipt_rows]),
        ).all()
    }
    for row in receipt_rows:
        if row.id in already_reversed:
            continue
        original = LedgerPosting(
            tenant_id=tenant_id,
            product_id=row.product_id,
            sku=row.sku,
            warehouse_id=row.warehouse_id,
            location_id=row.location_id,
            batch_no=row.batch_no,
            expiry_date=row.expiry_date.isoformat() if row.expiry_date else None,
            quantity=decimal_str(row.quantity),
            uom=row.uom,
            bucket=row.bucket,
            movement_type=row.movement_type,
            reference_type=row.reference_type,
            reference_id=row.reference_id,
            reference_no=row.reference_no,
            unit_cost=decimal_str(row.unit_cost) if row.unit_cost is not None else None,
            currency=row.currency,
        )
        inventory_ledger.reverse(original, original_id=row.id, reason=reason, actor_id=actor_id)


@router.post("/grns/{id}/cancel")
def cancel_grn(id: uuid_mod.UUID, body: CancelBody, actor: Actor = Depends(require_permission("grn:post"))):
    """Cancels a GRN that's either still under_qc or already posted. A
    posted cancellation is a true reversal: paired reversing ledger entries
    undo the stock receipt and the PO gets its received quantities back -
    blocked if any of the stock has since been consumed or put away."""
    tenant_id = actor["tenant_id"]
    grn = grn_repo.require_grn(tenant_id, id)
    assert_warehouse_in_scope(actor, grn.warehouse_id)
    assert_transition(grn.number, grn.status, "cancelled")

    lines = grn_repo.grn_lines(id)
    items = grn_repo.grn_items(id)

    if grn.status == "posted":
        if any(is_positive(i.consumed_qty) for i in items):
            raise rule_violation(
                f"{grn.number} cannot be cancelled — some of its stock has already been consumed downstream (production or an order). Raise a stock adjustment instead",
                code="GRN_ALREADY_CONSUMED",
            )
        if StockLedger.query.filter_by(tenant_id=tenant_id, reference_type="putaway", reference_no=grn.number).first():
            raise rule_violation(
                f"{grn.number} cannot be cancelled — its stock has already been put away into storage. Raise a stock adjustment instead",
                code="GRN_ALREADY_PUT_AWAY",
            )
        _reverse_grn_ledger_entries(tenant_id, grn, str(actor["user_id"]), body.reason)
        reverse_grn_receipt(tenant_id, grn.id)

    now = datetime.now(timezone.utc)
    for line in lines:
        line.deleted_at = now
    for item in items:
        item.deleted_at = now

    grn.status = "cancelled"
    grn.cancellation_reason = body.reason
    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="grn.cancelled", entity_type="grn", entity_id=str(id), reason=body.reason)
    session.commit()

    return grn_repo.to_grn_api(grn_repo.require_grn(tenant_id, id), grn_repo.grn_lines(id))


@router.post("/grns/{id}/putaway", status_code=201)
def putaway_grn(id: uuid_mod.UUID, body: PutawayBody, request: Request, raw_body: bytes = Depends(get_raw_body), actor: Actor = Depends(require_permission("grn:post"))):
    tenant_id = actor["tenant_id"]
    grn = grn_repo.require_grn(tenant_id, id)
    assert_warehouse_in_scope(actor, grn.warehouse_id)

    if grn.status != "posted":
        raise rule_violation(f"{grn.number} is {grn.status} — stock can only be put away after the receipt is posted", code="GRN_NOT_POSTED")

    def _do():
        lines = {str(l.id): l for l in grn_repo.grn_lines(id)}

        done_rows = (
            session.query(PutawayTask.grn_line_id, func.sum(PutawayTask.quantity))
            .filter(PutawayTask.tenant_id == tenant_id, PutawayTask.grn_id == id)
            .group_by(PutawayTask.grn_line_id)
            .all()
        )
        already_moved = {str(gl_id): to_decimal(moved) for gl_id, moved in done_rows}

        errors: list[dict] = []
        planned = []
        for index, input_ in enumerate(body.lines):
            field = f"lines.{index}"
            line = lines.get(str(input_.grnLineId))
            if not line:
                errors.append({"field": f"{field}.grnLineId", "message": f"No such line on {grn.number}"})
                continue

            accepted = to_decimal(line.accepted_qty)
            if not is_positive(accepted):
                errors.append({"field": f"{field}.grnLineId", "message": f"{line.sku} has no accepted quantity — there is nothing to put away"})
                continue

            moved = already_moved.get(str(line.id), to_decimal(0))
            outstanding = accepted - moved
            quantity = to_decimal(input_.quantity) if input_.quantity else outstanding

            if not is_positive(quantity):
                errors.append({"field": f"{field}.quantity", "message": "Quantity must be greater than zero"})
                continue
            if quantity > outstanding:
                errors.append({"field": f"{field}.quantity", "message": f"{line.sku}: {decimal_str(quantity)} {line.uom} exceeds the {decimal_str(outstanding)} {line.uom} still awaiting putaway ({decimal_str(accepted)} accepted, {decimal_str(moved)} already moved)"})
                continue

            target = warehouse_repo.find_location(tenant_id, input_.toLocationId)
            if not target:
                errors.append({"field": f"{field}.toLocationId", "message": "Location not found"})
                continue
            if target.warehouse_id != grn.warehouse_id:
                errors.append({"field": f"{field}.toLocationId", "message": f"{target.code} is in a different warehouse — putaway cannot move stock between sites, raise a transfer"})
                continue
            if target.status != "active":
                errors.append({"field": f"{field}.toLocationId", "message": f"{target.code} is {target.status}"})
                continue
            if target.type == "quarantine":
                errors.append({"field": f"{field}.toLocationId", "message": f"{target.code} is a quarantine location — accepted stock must not be put away there"})
                continue
            if target.id == line.location_id:
                errors.append({"field": f"{field}.toLocationId", "message": f"{line.sku} is already in {target.code}"})
                continue

            product = product_repo.get_summary(tenant_id, line.product_id)
            allowed = target.allowed_product_types or []
            if product and allowed and product["type"] not in allowed:
                errors.append({"field": f"{field}.toLocationId", "message": f"{target.code} accepts {', '.join(allowed)} — {line.sku} is a {product['type']}"})
                continue

            already_moved[str(line.id)] = moved + quantity
            planned.append({"line": line, "quantity": quantity, "to": target, "note": input_.note})

        assert_receipt_valid(errors, f"Putaway for {grn.number}")

        created = []
        for move in planned:
            line = move["line"]
            task = PutawayTask(
                tenant_id=tenant_id,
                grn_id=id,
                grn_line_id=line.id,
                warehouse_id=grn.warehouse_id,
                product_id=line.product_id,
                sku=line.sku,
                batch_no=line.batch_no,
                expiry_date=line.expiry_date,
                quantity=move["quantity"],
                uom=line.uom,
                from_location_id=line.location_id,
                from_location_code=line.location_code,
                to_location_id=move["to"].id,
                to_location_code=move["to"].code,
                completed_by=str(actor["user_id"]),
                note=move["note"],
            )
            session.add(task)
            session.flush()
            created.append(
                {
                    "putawayId": str(task.id),
                    "grnLineId": str(line.id),
                    "productId": str(line.product_id),
                    "sku": line.sku,
                    "batchNo": line.batch_no,
                    "expiryDate": line.expiry_date.isoformat() if line.expiry_date else None,
                    "quantity": decimal_str(move["quantity"]),
                    "uom": line.uom,
                    "fromLocationId": str(line.location_id) if line.location_id else None,
                    "fromLocationCode": line.location_code,
                    "toLocationId": str(move["to"].id),
                    "toLocationCode": move["to"].code,
                }
            )
            line.location_id = move["to"].id
            line.location_code = move["to"].code

        audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="grn.putaway", entity_type="grn", entity_id=str(id), meta={"number": grn.number, "moves": len(created)})

        payload = {"grnId": str(id), "grnNumber": grn.number, "warehouseId": str(grn.warehouse_id), "warehouseCode": grn.warehouse_code, "lines": created}
        inventory_ledger.post_putaway_transfer(tenant_id, payload)

        session.commit()
        return 201, {"grnId": str(id), "grnNumber": grn.number, "moves": created}

    status_code, response_body = run_idempotent(request.headers.get("Idempotency-Key"), "POST", request.url.path, raw_body, actor, _do)
    return JSONResponse(status_code=status_code, content=response_body)


@router.get("/grns/{id}/putaway")
def get_putaway(id: uuid_mod.UUID, actor: Actor = Depends(require_permission("grn:read"))):
    tenant_id = actor["tenant_id"]
    grn = grn_repo.require_grn(tenant_id, id)
    assert_warehouse_in_scope(actor, grn.warehouse_id)
    lines = grn_repo.grn_lines(id)
    moves = PutawayTask.query.filter_by(tenant_id=tenant_id, grn_id=id).order_by(PutawayTask.completed_at).all()

    moved_by_line: dict[uuid_mod.UUID, object] = {}
    for m in moves:
        moved_by_line[m.grn_line_id] = moved_by_line.get(m.grn_line_id, to_decimal(0)) + to_decimal(m.quantity)

    outstanding = []
    for l in lines:
        if not is_positive(l.accepted_qty):
            continue
        moved = moved_by_line.get(l.id, to_decimal(0))
        outstanding.append(
            {
                "grnLineId": str(l.id),
                "sku": l.sku,
                "uom": l.uom,
                "batchNo": l.batch_no,
                "acceptedQty": decimal_str(l.accepted_qty),
                "movedQty": decimal_str(moved),
                "outstandingQty": decimal_str(to_decimal(l.accepted_qty) - moved),
                "currentLocationId": str(l.location_id) if l.location_id else None,
                "currentLocationCode": l.location_code,
            }
        )

    return {
        "grnId": str(id),
        "grnNumber": grn.number,
        "status": grn.status,
        "complete": all(not is_positive(l["outstandingQty"]) for l in outstanding),
        "lines": outstanding,
        "moves": [
            {
                "id": str(m.id),
                "grnLineId": str(m.grn_line_id),
                "sku": m.sku,
                "quantity": decimal_str(m.quantity),
                "uom": m.uom,
                "fromLocationCode": m.from_location_code,
                "toLocationCode": m.to_location_code,
                "completedBy": m.completed_by,
                "completedAt": m.completed_at.isoformat() if m.completed_at else None,
            }
            for m in moves
        ],
    }


def _grn_audit_entry(row) -> dict:
    return {
        "id": str(row.id),
        "actor_id": str(row.actor_id) if row.actor_id else None,
        "actor_email": row.actor_email,
        "action": row.action,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "reason": row.reason,
        "correlation_id": row.correlation_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.get("/grns/{id}/audit")
def grn_audit(id: uuid_mod.UUID, actor: Actor = Depends(require_permission("grn:read"))):
    grn = grn_repo.require_grn(actor["tenant_id"], id)
    assert_warehouse_in_scope(actor, grn.warehouse_id)
    rows = read_audit_trail(tenant_id=actor["tenant_id"], entity_type="grn", entity_id=str(id))
    return {"data": [_grn_audit_entry(r) for r in rows]}


@router.get("/rejection-codes")
def list_rejection_codes(actor: Actor = Depends(require_permission("grn:read"))):
    rows = RejectionCode.query.filter_by(tenant_id=actor["tenant_id"]).order_by(RejectionCode.code).all()
    return {"data": [{"code": r.code, "description": r.description, "active": r.active} for r in rows]}


@router.post("/rejection-codes", status_code=201)
def create_rejection_code(body: RejectionCodeBody, actor: Actor = Depends(require_permission("warehouse:write"))):
    tenant_id = actor["tenant_id"]
    code = body.code.strip().upper()

    existing = RejectionCode.query.filter_by(tenant_id=tenant_id, code=code).first()
    if existing:
        existing.description = body.description
        existing.active = True
    else:
        session.add(RejectionCode(tenant_id=tenant_id, code=code, description=body.description))
    session.commit()

    return {"code": code, "description": body.description}
