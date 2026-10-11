"""Purchase orders: list/get/create/patch, submit/approve/reject/cancel/
short-close/amend, match-status, audit. Ported 1:1 (behavior) from
backend_py/app/routes/purchase_orders.py, minus the BigQuery write path
(out of scope - see the migration plan's scope decision #2, only the
Postgres `_create_po_postgres` branch is ported, as plain `_create_po`).

`issue`, `send-email` and `pdf` render the PO through document_repo/
document_pdf and email the vendor through notification_repo (in-process,
inline, like the original); a failed render/send never un-issues the PO -
it's recorded as email_state. Note `_create_po` already sets a new PO's
status straight to "issued" at creation (no draft stage, same "approval flow
removed" shape orders.py uses) - `submit`/`approve`/`reject` stay ported for
API-surface completeness.
"""

from __future__ import annotations

import csv
import io
import uuid as uuid_mod
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import or_

from app.core.auth import Actor, require_any_permission, require_permission
from app.core.access_scope import assert_warehouse_in_scope, scope_query_by_warehouse
from app.core.audit import audit, read_audit_trail
from app.core.config import settings
from app.core.db import session
from app.core.errors import ProblemError, rule_violation
from app.core.idempotency import get_raw_body, run_idempotent
from app.core.money import decimal_str, to_decimal
from app.core.pagination import ListQuery, list_response, offset_of
from app.domains.procurement.schemas import (
    AmendBody,
    ApproveBody,
    CancelBody,
    IssueBody,
    LineBody,
    PatchPoBody,
    PoBody,
    PoBulkUploadBody,
    RejectBody,
    ShortCloseBody,
)
from app.models.business_entity import BusinessEntity
from app.models.po_approval_record import PoApprovalRecord
from app.models.po_line import PoLine
from app.models.po_revision import PoRevision
from app.models.purchase_order import PurchaseOrder
from app.services import po_vendor_repo, document_pdf, document_repo, document_templates, notification_repo, org_repo, party_repo, party_summary, procurement_repo, product_repo, warehouse_repo
from app.services.po_approval import assert_not_self_approval, describe_tier, resolve_tier
from app.services.po_state import assert_editable, assert_transition
from app.services.po_tolerance import LineReceipt, open_quantity
from app.services.bq_writer import InsertOp, run_write_transaction
from app.services.sequences import next_document_number
from app.services.tax_codes import TaxableLine, compute_totals, is_known_tax_code, split_gst

router = APIRouter(prefix="/api/v1", tags=["procurement"])

_THRESHOLDS = {"l1": settings.po_approval_threshold_l1, "l2": settings.po_approval_threshold_l2, "l3": settings.po_approval_threshold_l3}

#  GRN & QC calls both of these directly to pick which PO to receive goods
#  against and to show that PO's own detail - not only the Procurement
#  module itself - so both accept warehouse:read too.
_PO_LOOKUP_PERMISSIONS = ("po:read", "warehouse:read")


def _validate_po(tenant_id, body, actor: Actor) -> dict:
    """Cross-module validation: vendor, warehouse and every product are
    checked and *all* failures are collected."""
    assert_warehouse_in_scope(actor, body.warehouseId)
    errors: list[dict] = []
    try:
        vendor = party_summary.build_summary_by_id(tenant_id, body.vendorId)
    except ProblemError:
        vendor = None
    warehouse_row = warehouse_repo.find_warehouse(tenant_id, body.warehouseId)
    warehouse = warehouse_repo.to_warehouse_api(warehouse_row) if warehouse_row else None
    products = product_repo.get_summaries(tenant_id, [l.productId for l in body.lines])

    if not vendor:
        errors.append({"field": "vendorId", "message": f"Vendor {body.vendorId} does not exist"})
    else:
        if vendor["type"] == "customer":
            errors.append({"field": "vendorId", "message": f"{vendor['code']} is a customer, not a vendor"})
        if vendor["status"] != "active":
            errors.append({"field": "vendorId", "message": f"{vendor['code']} is {vendor['status']}{' (blocked)' if vendor['blocked'] else ''} — only active vendors can receive purchase orders"})

    if not warehouse:
        errors.append({"field": "warehouseId", "message": f"Warehouse {body.warehouseId} does not exist"})
    elif warehouse["status"] != "active":
        errors.append({"field": "warehouseId", "message": f"Warehouse {warehouse['code']} is {warehouse['status']}"})

    if body.businessEntityId:
        entity = BusinessEntity.query.filter_by(tenant_id=tenant_id, id=body.businessEntityId).first()
        if not entity:
            errors.append({"field": "businessEntityId", "message": f"Business entity {body.businessEntityId} does not exist"})
        elif entity.status != "active":
            errors.append({"field": "businessEntityId", "message": f"Business entity {entity.code} is {entity.status}"})

    po_date = body.poDate or date.today()
    if body.expectedDate < po_date:
        errors.append({"field": "expectedDate", "message": f"Expected receipt ({body.expectedDate.isoformat()}) cannot be before the purchase order date ({po_date.isoformat()})"})

    resolved_lines = []
    for i, line in enumerate(body.lines):
        product = products.get(str(line.productId))
        field = f"lines.{i}"
        if not product:
            errors.append({"field": field, "message": f"Product {line.productId} does not exist"})
            resolved_lines.append({"line": line, "product": None, "taxCode": line.taxCode or "GST0"})
            continue
        if product["status"] != "active":
            errors.append({"field": field, "message": f"{product['sku']} is {product['status']} and cannot be purchased"})
        if not product["purchasable"]:
            errors.append({"field": field, "message": f"{product['sku']} is not flagged purchasable"})
        tax_code = line.taxCode or "GST0"
        if not is_known_tax_code(tax_code):
            errors.append({"field": f"{field}.taxCode", "message": f'"{tax_code}" is not a configured tax code'})
        if line.expectedDate and line.expectedDate < po_date:
            errors.append({"field": f"{field}.expectedDate", "message": "Line expected date cannot be before the PO date"})
        resolved_lines.append({"line": line, "product": product, "taxCode": tax_code})

    if errors:
        raise rule_violation(f"The purchase order has {len(errors)} problem{'s' if len(errors) > 1 else ''}: {'; '.join(e['message'] for e in errors)}", code="PO_VALIDATION_FAILED", meta={"errors": errors})

    totals = compute_totals([TaxableLine(quantity=r["line"].quantity, unit_price=r["line"].unitPrice, tax_code=r["taxCode"], discount=r["line"].discount) for r in resolved_lines], body.charges)

    if body.expectedTotal and to_decimal(body.expectedTotal) != to_decimal(totals.total):
        raise rule_violation(
            f"Total mismatch: the server computed {decimal_str(totals.total)} but the request declared {decimal_str(body.expectedTotal)}. Refresh the page — a price or tax code has changed",
            code="TOTAL_MISMATCH",
            meta={"computed": totals.total, "declared": body.expectedTotal, "breakdown": totals.by_tax_code},
        )

    return {"vendor": vendor, "warehouse": warehouse, "currency": body.currency or (vendor.get("currency") if vendor else None) or settings.base_currency, "totals": totals, "resolvedLines": resolved_lines}


def _compute_gst_split(tenant_id, vendor: dict | None, business_entity_id, tax_total) -> dict:
    seller = org_repo.resolve_seller(tenant_id, business_entity_id)
    vendor_state = vendor.get("stateCode") if vendor else None
    seller_state = seller.get("stateCode") if seller else None
    intra_state = bool(vendor_state and seller_state and vendor_state == seller_state)
    return split_gst(tax_total, intra_state)


def _insert_lines(tenant_id, po_id, lines: list[LineBody], validated: dict, carry_forward: dict | None = None) -> None:
    for i, line in enumerate(lines):
        computed = validated["totals"].lines[i]
        resolved = validated["resolvedLines"][i]
        sku = resolved["product"]["sku"] if resolved["product"] else ""
        carried = (carry_forward or {}).get(sku)
        session.add(
            PoLine(
                tenant_id=tenant_id,
                po_id=po_id,
                line_no=i + 1,
                product_id=line.productId,
                sku=sku,
                description=line.description or (resolved["product"]["name"] if resolved["product"] else None),
                quantity=line.quantity,
                uom=line.uom,
                unit_price=line.unitPrice,
                discount=line.discount,
                tax_code=resolved["taxCode"],
                tax_rate=computed.tax_rate,
                net_amount=computed.net_amount,
                tax_amount=computed.tax_amount,
                gross_amount=computed.gross_amount,
                expected_date=line.expectedDate,
                received_qty=carried["received"] if carried else "0",
                rejected_qty=carried["rejected"] if carried else "0",
                status="open",
            )
        )


def _line_to_input(line: PoLine) -> LineBody:
    return LineBody(productId=line.product_id, description=line.description, quantity=line.quantity, uom=line.uom, unitPrice=line.unit_price, discount=line.discount, taxCode=line.tax_code, expectedDate=line.expected_date)


@router.get("/purchase-orders")
def list_pos(
    actor: Actor = Depends(require_any_permission(*_PO_LOOKUP_PERMISSIONS)),
    query: ListQuery = Depends(),
    status: str | None = None,
    vendorId: uuid_mod.UUID | None = None,
    warehouseId: uuid_mod.UUID | None = None,
    from_: str | None = None,
    to_: str | None = None,
):
    tenant_id = actor["tenant_id"]

    q = PurchaseOrder.query.filter(PurchaseOrder.tenant_id == tenant_id)
    if status:
        statuses = [s.strip() for s in status.split(",") if s.strip()]
        if statuses:
            q = q.filter(PurchaseOrder.status.in_(statuses))
    if vendorId:
        q = q.filter(PurchaseOrder.vendor_id == vendorId)
    if warehouseId:
        assert_warehouse_in_scope(actor, warehouseId)
        q = q.filter(PurchaseOrder.warehouse_id == warehouseId)
    else:
        q = scope_query_by_warehouse(q, PurchaseOrder.warehouse_id, actor)
    if from_:
        q = q.filter(PurchaseOrder.po_date >= from_)
    if to_:
        q = q.filter(PurchaseOrder.po_date <= to_)
    if query.q:
        like = f"%{query.q}%"
        line_match = session.query(PoLine.po_id).filter(PoLine.sku.ilike(like))
        q = q.filter(or_(PurchaseOrder.number.ilike(like), PurchaseOrder.vendor_name.ilike(like), PurchaseOrder.id.in_(line_match)))

    total = q.count()
    sort = (query.sort or "").lstrip("-")
    sortable = {"number": PurchaseOrder.number, "po_date": PurchaseOrder.po_date, "expected_date": PurchaseOrder.expected_date, "total": PurchaseOrder.total, "status": PurchaseOrder.status, "created_at": PurchaseOrder.created_at}
    column = sortable.get(sort, PurchaseOrder.po_date)
    order = column.desc() if (query.sort or "").startswith("-") or not query.sort else column.asc()
    rows = q.order_by(order).limit(query.limit).offset(offset_of(query)).all()

    from sqlalchemy import func

    outstanding_by_po = dict(
        session.query(
            PoLine.po_id,
            func.coalesce(func.sum((PoLine.quantity - PoLine.received_qty - PoLine.rejected_qty) * PoLine.unit_price), 0),
        )
        .filter(PoLine.po_id.in_([r.id for r in rows]), PoLine.status != "cancelled")
        .group_by(PoLine.po_id)
        .all()
    ) if rows else {}

    vendor_state = po_vendor_repo.summaries([r.id for r in rows])
    data = [
        procurement_repo.to_po_api(r, outstanding_value=decimal_str(outstanding_by_po.get(r.id) or 0)) | vendor_state[r.id]
        for r in rows
    ]
    return list_response(data, query, total)


@router.get("/purchase-orders/{id}")
def get_po(id: uuid_mod.UUID, actor: Actor = Depends(require_any_permission(*_PO_LOOKUP_PERMISSIONS))):
    tenant_id = actor["tenant_id"]
    po = procurement_repo.require_po(tenant_id, id)
    assert_warehouse_in_scope(actor, po.warehouse_id)
    lines = procurement_repo.lines_of(id)
    result = procurement_repo.to_po_api(po, lines)
    result.update(po_vendor_repo.summaries([po.id])[po.id])
    result["approvalTierDescription"] = describe_tier(po.approval_tier, _THRESHOLDS)
    approvals = PoApprovalRecord.query.filter_by(po_id=id).order_by(PoApprovalRecord.created_at).all()
    result["approvals"] = [{"tier": a.tier, "actor": a.actor, "decision": a.decision, "reason": a.reason, "createdAt": a.created_at.isoformat() if a.created_at else None} for a in approvals]
    return result


class _CreatedPoRef:
    """Enough of PurchaseOrder's interface (id, number) for callers to
    re-fetch the full row via procurement_repo.require_po/lines_of after
    creation - both backends return this shape from _create_po, so the
    read-side callers (create_po route, bulk upload) don't need to care
    which one ran. Reads work the same via the ORM regardless of backend;
    only the write itself differs (see _create_po_bigquery)."""

    def __init__(self, id: uuid_mod.UUID, number: str):
        self.id = id
        self.number = number


def _create_po_postgres(tenant_id, actor: dict, body: PoBody, before_commit=None) -> PurchaseOrder:
    """`before_commit(po)` lets a caller (sourcing) record its own link to the new PO in the same transaction."""
    validated = _validate_po(tenant_id, body, actor)
    number = next_document_number(tenant_id, settings.po_number_prefix, pad=4, start=3000)
    now = datetime.now(timezone.utc)
    gst_split = _compute_gst_split(tenant_id, validated["vendor"], body.businessEntityId, validated["totals"].tax_total)
    po = PurchaseOrder(
        tenant_id=tenant_id,
        number=number,
        vendor_id=body.vendorId,
        vendor_name=validated["vendor"]["displayName"],
        warehouse_id=body.warehouseId,
        warehouse_code=validated["warehouse"]["code"],
        business_entity_id=body.businessEntityId,
        # Approval flow removed: a PO is approved and issued (live) on
        # creation - faithful port (same shape as BOM's auto-approve).
        status="issued",
        po_date=body.poDate or date.today(),
        expected_date=body.expectedDate,
        currency=validated["currency"],
        exchange_rate=body.exchangeRate,
        subtotal=validated["totals"].subtotal,
        tax_total=validated["totals"].tax_total,
        cgst=gst_split["cgst"],
        sgst=gst_split["sgst"],
        igst=gst_split["igst"],
        charges=body.charges,
        total=validated["totals"].total,
        payment_terms=body.paymentTerms or validated["vendor"].get("paymentTerms"),
        payment_mode=body.paymentMode,
        incoterms=body.incoterms,
        notes=body.notes,
        approval_tier=resolve_tier(validated["totals"].total, _THRESHOLDS),
        created_by=str(actor["user_id"]),
        approved_by=str(actor["user_id"]),
        approved_at=now,
        issued_at=now,
        email_state="not_sent",
    )
    session.add(po)
    session.flush()
    _insert_lines(tenant_id, po.id, body.lines, validated)

    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="po.created", entity_type="purchase-order", entity_id=str(po.id), meta={"number": number, "vendor": validated["vendor"]["displayName"], "total": validated["totals"].total, "lines": len(body.lines)})
    if before_commit:
        before_commit(po)
    session.commit()

    # Freezing the SKU is a consequence of the PO existing, not a
    # precondition for it - done after commit so a Product outage cannot
    # block procurement.
    for line in body.lines:
        try:
            product_repo.mark_transacted(tenant_id, line.productId, number)
        except Exception:
            pass
    session.commit()

    return po


def _create_po_bigquery(tenant_id, actor: dict, body: PoBody) -> _CreatedPoRef:
    """BigQuery counterpart to _create_po_postgres. _validate_po and
    _compute_gst_split are pure reads/computation, unchanged for either
    backend; only the write (PO header + lines + audit row) is a script run
    through bq_writer.run_write_transaction. See
    /Users/Peeyush/.claude/plans/mossy-stirring-gosling.md (Phase 4) - the
    representative "multi-table insert with a sequence number" module,
    covering the shape most of this codebase's ~123 write sites follow.

    The post-commit mark_transacted() SKU-freeze loop is deliberately not
    ported here yet: it's a separate, best-effort side effect (failures are
    swallowed even in the Postgres path) on the products table, following
    the same InsertOp/UpdateOp pattern already established - defer it to
    when the Products module itself is cut over, rather than duplicate that
    table's write logic here first.

    build_ops() redoes numbering/validation itself so a retry after a
    conflict sees the latest committed state, not a stale snapshot."""
    created_ref: dict = {}

    def build_ops() -> list[InsertOp]:
        validated = _validate_po(tenant_id, body, actor)
        number = next_document_number(tenant_id, settings.po_number_prefix, pad=4, start=3000)
        now = datetime.now(timezone.utc)
        gst_split = _compute_gst_split(tenant_id, validated["vendor"], body.businessEntityId, validated["totals"].tax_total)
        po_date = body.poDate or date.today()
        new_id = uuid_mod.uuid4()

        po_values = {
            "id": new_id,
            "tenant_id": tenant_id,
            "number": number,
            "revision": 0,
            "vendor_id": body.vendorId,
            "vendor_name": validated["vendor"]["displayName"],
            "warehouse_id": body.warehouseId,
            "warehouse_code": validated["warehouse"]["code"],
            "business_entity_id": body.businessEntityId,
            "status": "issued",
            "po_date": po_date,
            "expected_date": body.expectedDate,
            "currency": validated["currency"],
            "exchange_rate": body.exchangeRate,
            "subtotal": validated["totals"].subtotal,
            "tax_total": validated["totals"].tax_total,
            "cgst": gst_split["cgst"],
            "sgst": gst_split["sgst"],
            "igst": gst_split["igst"],
            "charges": body.charges,
            "total": validated["totals"].total,
            "payment_terms": body.paymentTerms or validated["vendor"].get("paymentTerms"),
            "payment_mode": body.paymentMode,
            "incoterms": body.incoterms,
            "notes": body.notes,
            "approval_tier": resolve_tier(validated["totals"].total, _THRESHOLDS),
            "created_by": str(actor["user_id"]),
            "approved_by": str(actor["user_id"]),
            "approved_at": now,
            "issued_at": now,
            "email_state": "not_sent",
            "receipt_status": "none",
            "created_at": now,
            "updated_at": now,
        }
        ops: list[InsertOp] = [InsertOp(table="purchase_orders", values=po_values)]

        for i, line in enumerate(body.lines):
            computed = validated["totals"].lines[i]
            resolved = validated["resolvedLines"][i]
            sku = resolved["product"]["sku"] if resolved["product"] else ""
            ops.append(
                InsertOp(
                    table="po_lines",
                    values={
                        "id": uuid_mod.uuid4(),
                        "tenant_id": tenant_id,
                        "po_id": new_id,
                        "line_no": i + 1,
                        "product_id": line.productId,
                        "sku": sku,
                        "description": line.description or (resolved["product"]["name"] if resolved["product"] else None),
                        "quantity": line.quantity,
                        "uom": line.uom,
                        "unit_price": line.unitPrice,
                        "discount": line.discount,
                        "tax_code": resolved["taxCode"],
                        "tax_rate": computed.tax_rate,
                        "net_amount": computed.net_amount,
                        "tax_amount": computed.tax_amount,
                        "gross_amount": computed.gross_amount,
                        "expected_date": line.expectedDate,
                        "received_qty": "0",
                        "rejected_qty": "0",
                        "status": "open",
                    },
                )
            )

        ops.append(
            InsertOp(
                table="audit_log",
                values={
                    "id": uuid_mod.uuid4(),
                    "tenant_id": tenant_id,
                    "actor_id": actor["user_id"],
                    "actor_email": actor["email"],
                    "action": "po.created",
                    "entity_type": "purchase-order",
                    "entity_id": str(new_id),
                    "created_at": now,
                    "meta": {
                        "number": number,
                        "vendor": validated["vendor"]["displayName"],
                        "total": str(validated["totals"].total),
                        "lines": len(body.lines),
                    },
                },
            )
        )

        created_ref.clear()
        created_ref.update({"id": new_id, "number": number})
        return ops

    run_write_transaction(settings.bigquery_dataset_id, build_ops)
    return _CreatedPoRef(id=created_ref["id"], number=created_ref["number"])


def _create_po(tenant_id, actor: dict, body: PoBody):
    """Shared by the single-PO create route and the bulk-upload route, so a
    PO created either way goes through the exact same validation, numbering,
    GST-split and audit trail. Returns an object with at least .id/.number -
    callers re-fetch via procurement_repo for the full row either way."""
    if settings.db_backend == "bigquery":
        return _create_po_bigquery(tenant_id, actor, body)
    return _create_po_postgres(tenant_id, actor, body)


@router.post("/purchase-orders", status_code=201)
def create_po(body: PoBody, request: Request, raw_body: bytes = Depends(get_raw_body), actor: Actor = Depends(require_permission("po:write"))):
    tenant_id = actor["tenant_id"]

    def _do():
        po = _create_po(tenant_id, actor, body)
        return 201, procurement_repo.to_po_api(procurement_repo.require_po(tenant_id, po.id), procurement_repo.lines_of(po.id))

    status_code, response_body = run_idempotent(request.headers.get("Idempotency-Key"), "POST", request.url.path, raw_body, actor, _do)
    return JSONResponse(status_code=status_code, content=response_body)


BULK_UPLOAD_REQUIRED_COLUMNS = ["poRef", "vendorCode", "warehouseCode", "expectedDate", "productSku", "quantity", "unitPrice"]


@router.post("/purchase-orders/bulk-upload")
def bulk_upload_pos(body: PoBulkUploadBody, actor: Actor = Depends(require_permission("po:write"))):
    """Creates many POs from one CSV in a single request. Each poRef group is
    independent - one bad group is reported as an error and skipped."""
    tenant_id = actor["tenant_id"]

    reader = csv.DictReader(io.StringIO(body.csvContent))
    fieldnames = [(f or "").strip() for f in (reader.fieldnames or [])]
    missing_columns = [c for c in BULK_UPLOAD_REQUIRED_COLUMNS if c not in fieldnames]
    if missing_columns:
        raise rule_violation(f"CSV is missing required column(s): {', '.join(missing_columns)}", code="BULK_CSV_INVALID_HEADERS")

    groups: dict[str, list[dict]] = {}
    order: list[str] = []
    stray_rows: list[dict] = []
    for row_number, raw_row in enumerate(reader, start=2):
        row = {(k or "").strip(): (v or "").strip() for k, v in raw_row.items() if k}
        row["_rowNumber"] = row_number
        ref = row.get("poRef") or ""
        if not ref:
            if any(v for k, v in row.items() if k != "_rowNumber"):
                stray_rows.append(row)
            continue
        if ref not in groups:
            groups[ref] = []
            order.append(ref)
        groups[ref].append(row)

    vendors_by_code = party_repo.find_parties_by_codes(tenant_id, [groups[r][0].get("vendorCode") or "" for r in order])
    warehouses_by_code = warehouse_repo.find_warehouses_by_codes(tenant_id, [groups[r][0].get("warehouseCode") or "" for r in order])
    entities_by_code = org_repo.find_entities_by_codes(tenant_id, [groups[r][0].get("businessEntityCode") or "" for r in order])
    products_by_sku = product_repo.find_by_skus(tenant_id, [r.get("productSku") or "" for ref in order for r in groups[ref]])

    results = []
    for ref in order:
        rows = groups[ref]
        first = rows[0]
        errors: list[str] = []

        vendor_code = first.get("vendorCode") or ""
        vendor = vendors_by_code.get(vendor_code.upper()) if vendor_code else None
        if not vendor_code:
            errors.append("vendorCode is required")
        elif not vendor:
            errors.append(f"Vendor code '{vendor_code}' not found")

        warehouse_code = first.get("warehouseCode") or ""
        warehouse = warehouses_by_code.get(warehouse_code.upper()) if warehouse_code else None
        if not warehouse_code:
            errors.append("warehouseCode is required")
        elif not warehouse:
            errors.append(f"Warehouse code '{warehouse_code}' not found")

        entity_code = first.get("businessEntityCode") or ""
        entity = None
        if entity_code:
            entity = entities_by_code.get(entity_code)
            if not entity:
                errors.append(f"Business entity code '{entity_code}' not found")

        expected_date_raw = first.get("expectedDate") or ""
        expected_date = None
        try:
            expected_date = date.fromisoformat(expected_date_raw)
        except ValueError:
            errors.append(f"Invalid expectedDate '{expected_date_raw}' — use YYYY-MM-DD")

        lines: list[LineBody] = []
        for r in rows:
            row_no = r["_rowNumber"]
            sku = r.get("productSku") or ""
            if not sku:
                errors.append(f"Row {row_no}: productSku is required")
                continue
            product = products_by_sku.get(sku.upper())
            if not product:
                errors.append(f"Row {row_no}: product SKU '{sku}' not found")
                continue
            quantity_raw = r.get("quantity") or ""
            unit_price_raw = r.get("unitPrice") or ""
            if not quantity_raw:
                errors.append(f"Row {row_no}: quantity is required")
                continue
            if not unit_price_raw:
                errors.append(f"Row {row_no}: unitPrice is required")
                continue
            uom = (r.get("uom") or "").strip() or product.uom
            try:
                lines.append(LineBody(productId=product.id, quantity=quantity_raw, uom=uom, unitPrice=unit_price_raw, taxCode=r.get("taxCode") or None))
            except ValidationError as exc:
                errors.append(f"Row {row_no}: {exc.errors()[0].get('msg', 'invalid line data')}")

        if not errors and not lines:
            errors.append("No line items")

        if errors:
            results.append({"poRef": ref, "status": "error", "error": "; ".join(errors), "rows": rows})
            continue

        try:
            po_body = PoBody(
                vendorId=vendor.id,
                warehouseId=warehouse.id,
                businessEntityId=entity.id if entity else None,
                expectedDate=expected_date,
                paymentTerms=first.get("paymentTerms") or None,
                paymentMode=first.get("paymentMode") or None,
                lines=lines,
            )
        except ValidationError as exc:
            results.append({"poRef": ref, "status": "error", "error": exc.errors()[0].get("msg", "invalid PO data"), "rows": rows})
            continue

        try:
            po = _create_po(tenant_id, actor, po_body)
            results.append({"poRef": ref, "status": "success", "poNumber": po.number, "rows": rows})
        except ProblemError as exc:
            session.rollback()
            results.append({"poRef": ref, "status": "error", "error": exc.detail, "rows": rows})
        except Exception as exc:  # noqa: BLE001 - one bad group must not fail the whole batch
            session.rollback()
            results.append({"poRef": ref, "status": "error", "error": str(exc), "rows": rows})

    for row in stray_rows:
        results.append({"poRef": f"(row {row['_rowNumber']})", "status": "error", "error": "Missing poRef", "rows": [row]})

    success_count = sum(1 for r in results if r["status"] == "success")
    error_count = len(results) - success_count
    return {
        "summary": {"totalGroups": len(results), "successCount": success_count, "errorCount": error_count},
        "results": [
            {
                "poRef": r["poRef"],
                "status": r["status"],
                "poNumber": r.get("poNumber"),
                "error": r.get("error"),
                "rows": [{k: v for k, v in row.items() if k != "_rowNumber"} for row in r["rows"]] if r["status"] == "error" else [],
            }
            for r in results
        ],
    }


@router.patch("/purchase-orders/{id}")
def patch_po(id: uuid_mod.UUID, body: PatchPoBody, actor: Actor = Depends(require_permission("po:write"))):
    tenant_id = actor["tenant_id"]
    po = procurement_repo.require_po(tenant_id, id)
    assert_warehouse_in_scope(actor, po.warehouse_id)
    assert_editable(po.number, po.status)

    class _Merged:
        pass

    merged = _Merged()
    merged.vendorId = body.vendorId or po.vendor_id
    merged.warehouseId = body.warehouseId or po.warehouse_id
    merged.businessEntityId = body.businessEntityId if body.businessEntityId is not None else po.business_entity_id
    merged.expectedDate = body.expectedDate or po.expected_date
    merged.poDate = body.poDate or po.po_date
    merged.currency = body.currency or po.currency
    merged.exchangeRate = body.exchangeRate or decimal_str(po.exchange_rate)
    merged.charges = body.charges if body.charges is not None else decimal_str(po.charges)
    merged.lines = body.lines if body.lines is not None else [_line_to_input(l) for l in procurement_repo.lines_of(id)]
    merged.expectedTotal = body.expectedTotal

    validated = _validate_po(tenant_id, merged, actor)

    po.vendor_id = merged.vendorId
    po.vendor_name = validated["vendor"]["displayName"]
    po.warehouse_id = merged.warehouseId
    po.warehouse_code = validated["warehouse"]["code"]
    po.business_entity_id = merged.businessEntityId
    po.po_date = merged.poDate
    po.expected_date = merged.expectedDate
    po.currency = validated["currency"]
    po.exchange_rate = merged.exchangeRate
    po.subtotal = validated["totals"].subtotal
    po.tax_total = validated["totals"].tax_total
    gst_split = _compute_gst_split(tenant_id, validated["vendor"], merged.businessEntityId, validated["totals"].tax_total)
    po.cgst = gst_split["cgst"]
    po.sgst = gst_split["sgst"]
    po.igst = gst_split["igst"]
    po.charges = merged.charges
    po.total = validated["totals"].total
    po.approval_tier = resolve_tier(validated["totals"].total, _THRESHOLDS)
    if body.paymentTerms is not None:
        po.payment_terms = body.paymentTerms
    if body.paymentMode is not None:
        po.payment_mode = body.paymentMode
    if "incoterms" in body.model_fields_set:
        po.incoterms = body.incoterms
    if "notes" in body.model_fields_set:
        po.notes = body.notes

    if body.lines is not None:
        PoLine.query.filter_by(po_id=id).delete()
        session.flush()
        _insert_lines(tenant_id, id, body.lines, validated)

    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="po.updated", entity_type="purchase-order", entity_id=str(id))
    session.commit()

    return procurement_repo.to_po_api(procurement_repo.require_po(tenant_id, id), procurement_repo.lines_of(id))


@router.post("/purchase-orders/{id}/submit")
def submit_po(id: uuid_mod.UUID, actor: Actor = Depends(require_permission("po:write"))):
    tenant_id = actor["tenant_id"]
    po = procurement_repo.require_po(tenant_id, id)
    assert_warehouse_in_scope(actor, po.warehouse_id)
    tier = resolve_tier(po.total, _THRESHOLDS)

    target = "approved" if tier == 0 else "pending_approval"
    assert_transition(po.number, po.status, target)

    po.status = target
    po.approval_tier = tier
    if tier == 0:
        po.approved_by = "auto"
        po.approved_at = datetime.now(timezone.utc)

    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="po.auto-approved" if tier == 0 else "po.submitted", entity_type="purchase-order", entity_id=str(id), meta={"tier": tier, "total": decimal_str(po.total)})
    session.commit()

    return procurement_repo.to_po_api(procurement_repo.require_po(tenant_id, id), procurement_repo.lines_of(id))


@router.post("/purchase-orders/{id}/approve")
def approve_po(id: uuid_mod.UUID, body: ApproveBody, actor: Actor = Depends(require_permission("po:approve"))):
    tenant_id = actor["tenant_id"]
    po = procurement_repo.require_po(tenant_id, id)
    assert_warehouse_in_scope(actor, po.warehouse_id)
    assert_transition(po.number, po.status, "approved")
    assert_not_self_approval(po.created_by, str(actor["user_id"]), po.number)

    po.status = "approved"
    po.approved_by = str(actor["user_id"])
    po.approved_at = datetime.now(timezone.utc)
    session.add(PoApprovalRecord(tenant_id=tenant_id, po_id=id, tier=po.approval_tier, actor=str(actor["user_id"]), decision="approved", reason=body.reason))

    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="po.approved", entity_type="purchase-order", entity_id=str(id), meta={"tier": po.approval_tier, "total": decimal_str(po.total)}, reason=body.reason)
    session.commit()

    return procurement_repo.to_po_api(procurement_repo.require_po(tenant_id, id), procurement_repo.lines_of(id))


@router.post("/purchase-orders/{id}/reject")
def reject_po(id: uuid_mod.UUID, body: RejectBody, actor: Actor = Depends(require_permission("po:approve"))):
    tenant_id = actor["tenant_id"]
    po = procurement_repo.require_po(tenant_id, id)
    assert_warehouse_in_scope(actor, po.warehouse_id)
    assert_transition(po.number, po.status, "draft")

    po.status = "draft"
    session.add(PoApprovalRecord(tenant_id=tenant_id, po_id=id, tier=po.approval_tier, actor=str(actor["user_id"]), decision="rejected", reason=body.reason))
    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="po.rejected", entity_type="purchase-order", entity_id=str(id), reason=body.reason)
    session.commit()

    return procurement_repo.to_po_api(procurement_repo.require_po(tenant_id, id), procurement_repo.lines_of(id))


@router.post("/purchase-orders/{id}/cancel")
def cancel_po(id: uuid_mod.UUID, body: CancelBody, actor: Actor = Depends(require_permission("po:cancel"))):
    tenant_id = actor["tenant_id"]
    po = procurement_repo.require_po(tenant_id, id)
    assert_warehouse_in_scope(actor, po.warehouse_id)
    assert_transition(po.number, po.status, "cancelled")

    lines = procurement_repo.lines_of(id)
    received = [l for l in lines if to_decimal(l.received_qty) > 0]
    if received:
        raise rule_violation(
            f"{po.number} cannot be cancelled — {len(received)} line(s) have already been received ({', '.join(f'{l.sku}: {decimal_str(l.received_qty)} {l.uom}' for l in received)}). Raise a return against the goods receipt instead",
            code="RECEIPT_EXISTS",
        )

    po.status = "cancelled"
    po.cancelled_reason = body.reason
    po.cancelled_at = datetime.now(timezone.utc)
    PoLine.query.filter_by(po_id=id).update({"status": "cancelled"})
    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="po.cancelled", entity_type="purchase-order", entity_id=str(id), reason=body.reason)
    session.commit()

    return procurement_repo.to_po_api(procurement_repo.require_po(tenant_id, id), procurement_repo.lines_of(id))


@router.post("/purchase-orders/{id}/short-close")
def short_close_po(id: uuid_mod.UUID, body: ShortCloseBody, actor: Actor = Depends(require_permission("po:short_close"))):
    """Force-closes a PO that still has an outstanding balance."""
    tenant_id = actor["tenant_id"]
    po = procurement_repo.require_po(tenant_id, id)
    assert_warehouse_in_scope(actor, po.warehouse_id)
    assert_transition(po.number, po.status, "closed")

    lines = procurement_repo.lines_of(id)
    open_lines = [
        (l, open_quantity(LineReceipt(line_id=str(l.id), sku=l.sku, ordered_qty=decimal_str(l.quantity), received_qty=decimal_str(l.received_qty), rejected_qty=decimal_str(l.rejected_qty))))
        for l in lines
    ]
    open_lines = [(l, qty) for l, qty in open_lines if to_decimal(qty) > 0]
    if not open_lines:
        raise rule_violation(f"{po.number} has nothing outstanding to short-close — it is already fully received", code="PO_FULLY_RECEIVED")

    po.status = "closed"
    PoLine.query.filter(PoLine.po_id == id, PoLine.status.in_(("open", "partial"))).update({"status": "closed"}, synchronize_session=False)
    audit(
        tenant_id=tenant_id,
        actor_id=actor["user_id"],
        actor_email=actor["email"],
        action="po.short_closed",
        entity_type="purchase-order",
        entity_id=str(id),
        reason=body.reason,
        meta={"openLines": [{"lineId": str(l.id), "sku": l.sku, "openQty": decimal_str(qty)} for l, qty in open_lines]},
    )
    session.commit()

    return procurement_repo.to_po_api(procurement_repo.require_po(tenant_id, id), procurement_repo.lines_of(id))


@router.post("/purchase-orders/{id}/amend", status_code=201)
def amend_po(id: uuid_mod.UUID, body: AmendBody, actor: Actor = Depends(require_permission("po:write"))):
    """Amending an issued PO creates a *successor* document rather than
    editing the one the vendor is holding."""
    tenant_id = actor["tenant_id"]
    po = procurement_repo.require_po(tenant_id, id)
    assert_warehouse_in_scope(actor, po.warehouse_id)
    if po.status in ("cancelled", "closed"):
        raise rule_violation(f"{po.number} is {po.status} and cannot be amended", code="PO_STATE_INVALID")
    current_lines = procurement_repo.lines_of(id)

    class _Merged:
        pass

    merged = _Merged()
    merged.vendorId = body.vendorId or po.vendor_id
    merged.warehouseId = body.warehouseId or po.warehouse_id
    merged.businessEntityId = body.businessEntityId if body.businessEntityId is not None else po.business_entity_id
    merged.poDate = po.po_date
    merged.expectedDate = body.expectedDate or po.expected_date
    merged.currency = body.currency or po.currency
    merged.exchangeRate = body.exchangeRate or decimal_str(po.exchange_rate)
    merged.charges = body.charges if body.charges is not None else decimal_str(po.charges)
    merged.paymentTerms = body.paymentTerms or po.payment_terms
    merged.paymentMode = body.paymentMode or po.payment_mode
    merged.incoterms = body.incoterms or po.incoterms
    merged.notes = body.notes or po.notes
    merged.lines = body.lines if body.lines is not None else [_line_to_input(l) for l in current_lines]
    merged.expectedTotal = None

    validated = _validate_po(tenant_id, merged, actor)
    gst_split = _compute_gst_split(tenant_id, validated["vendor"], merged.businessEntityId, validated["totals"].tax_total)

    received_by_sku = {l.sku: {"received": decimal_str(l.received_qty), "rejected": decimal_str(l.rejected_qty)} for l in current_lines}

    procurement_repo.lock_po(tenant_id, id)
    session.add(PoRevision(tenant_id=tenant_id, po_id=id, revision=po.revision, snapshot=procurement_repo.to_po_api(po, current_lines), reason=body.reason, created_by=str(actor["user_id"])))

    successor = PurchaseOrder(
        tenant_id=tenant_id,
        number=po.number,
        revision=po.revision + 1,
        supersedes_id=id,
        vendor_id=merged.vendorId,
        vendor_name=validated["vendor"]["displayName"],
        warehouse_id=merged.warehouseId,
        warehouse_code=validated["warehouse"]["code"],
        business_entity_id=merged.businessEntityId,
        status="pending_approval",
        po_date=merged.poDate,
        expected_date=merged.expectedDate,
        currency=validated["currency"],
        exchange_rate=merged.exchangeRate,
        subtotal=validated["totals"].subtotal,
        tax_total=validated["totals"].tax_total,
        cgst=gst_split["cgst"],
        sgst=gst_split["sgst"],
        igst=gst_split["igst"],
        charges=merged.charges,
        total=validated["totals"].total,
        payment_terms=merged.paymentTerms,
        payment_mode=merged.paymentMode,
        incoterms=merged.incoterms,
        notes=merged.notes,
        approval_tier=resolve_tier(validated["totals"].total, _THRESHOLDS),
        created_by=str(actor["user_id"]),
    )
    session.add(successor)
    session.flush()
    _insert_lines(tenant_id, successor.id, merged.lines, validated, received_by_sku)

    po.status = "closed"
    po.notes = (po.notes or "") + f" [superseded by revision {po.revision + 1}]"

    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="po.amended", entity_type="purchase-order", entity_id=str(id), meta={"successorId": str(successor.id), "revision": po.revision + 1}, reason=body.reason)
    session.commit()

    return procurement_repo.to_po_api(procurement_repo.require_po(tenant_id, successor.id), procurement_repo.lines_of(successor.id))


@router.get("/purchase-orders/{id}/match-status")
def match_status(id: uuid_mod.UUID, actor: Actor = Depends(require_permission("po:read"))):
    """Three-way match: ordered vs received vs invoiced, per line. `finance`
    (the source of invoiced quantities) isn't ported yet, so `matchable` is
    always false - same "Finance unreachable" fallback the original preserves."""
    tenant_id = actor["tenant_id"]
    po = procurement_repo.require_po(tenant_id, id)
    assert_warehouse_in_scope(actor, po.warehouse_id)
    lines = procurement_repo.lines_of(id)
    invoiced = None  # finance module out of scope

    rows = []
    for line in lines:
        ordered = to_decimal(line.quantity)
        received = to_decimal(line.received_qty)
        rows.append(
            {
                "lineId": str(line.id),
                "sku": line.sku,
                "uom": line.uom,
                "orderedQty": decimal_str(ordered),
                "receivedQty": decimal_str(received),
                "rejectedQty": decimal_str(line.rejected_qty),
                "invoicedQty": None,
                "openQty": decimal_str(open_quantity(LineReceipt(line_id=str(line.id), sku=line.sku, ordered_qty=decimal_str(line.quantity), received_qty=decimal_str(line.received_qty), rejected_qty=decimal_str(line.rejected_qty)))),
                "matched": False,
            }
        )

    return {"poId": str(id), "number": po.number, "matchable": invoiced is not None, "matched": False, "lines": rows}


@router.get("/purchase-orders/{id}/audit")
def po_audit(id: uuid_mod.UUID, actor: Actor = Depends(require_permission("po:read"))):
    po = procurement_repo.require_po(actor["tenant_id"], id)
    assert_warehouse_in_scope(actor, po.warehouse_id)
    rows = read_audit_trail(tenant_id=actor["tenant_id"], entity_type="purchase-order", entity_id=str(id))
    return {"data": [{"id": str(r.id), "actor_id": str(r.actor_id) if r.actor_id else None, "actor_email": r.actor_email, "action": r.action, "reason": r.reason, "created_at": r.created_at.isoformat() if r.created_at else None} for r in rows]}


@router.post("/purchase-orders/{id}/issue")
def issue_po(id: uuid_mod.UUID, body: IssueBody, actor: Actor = Depends(require_permission("po:issue"))):
    """Issuing is the commitment. The PO becomes immutable and (best-effort) a
    PDF is rendered and the vendor emailed - neither side effect can un-issue
    it, so both are recorded as state on the PO rather than rolled back."""
    tenant_id = actor["tenant_id"]
    po = procurement_repo.require_po(tenant_id, id)
    assert_warehouse_in_scope(actor, po.warehouse_id)
    assert_transition(po.number, po.status, "issued")

    po.status = "issued"
    po.issued_at = datetime.now(timezone.utc)
    po.email_state = "queued"
    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="po.issued", entity_type="purchase-order", entity_id=str(id), meta={"total": decimal_str(po.total)})
    session.commit()

    _dispatch_po(tenant_id, id, body.to, body.cc)
    session.commit()
    return procurement_repo.to_po_api(procurement_repo.require_po(tenant_id, id), procurement_repo.lines_of(id))


@router.post("/purchase-orders/{id}/send-email")
def send_email_po(id: uuid_mod.UUID, body: IssueBody, actor: Actor = Depends(require_permission("po:email"))):
    tenant_id = actor["tenant_id"]
    po = procurement_repo.require_po(tenant_id, id)
    assert_warehouse_in_scope(actor, po.warehouse_id)
    if po.status in ("draft", "pending_approval"):
        raise rule_violation(f"{po.number} has not been issued yet — approve and issue it first", code="PO_NOT_ISSUED")
    result = _dispatch_po(tenant_id, id, body.to, body.cc)
    session.commit()
    return {"poId": str(id), **result}


@router.get("/purchase-orders/{id}/pdf")
def po_pdf(id: uuid_mod.UUID, actor: Actor = Depends(require_permission("po:read"))):
    """Renders fresh on every call rather than serving a cached copy - a plain
    download should always reflect the PO's current data, not a stale render
    from whenever it was last issued/emailed (which does still archive its
    own copy to document storage, separately, via _dispatch_po)."""
    tenant_id = actor["tenant_id"]
    po = procurement_repo.require_po(tenant_id, id)
    assert_warehouse_in_scope(actor, po.warehouse_id)
    document_data = _build_po_document_data(tenant_id, po)
    html = document_templates.TEMPLATES["purchase-order"](document_data)
    result = document_pdf.html_to_pdf(html)
    extension = "pdf" if result["engine"] != "html" else "html"
    return Response(content=result["body"], media_type=result["content_type"], headers={"Content-Disposition": f'attachment; filename="{po.number}.{extension}"'})


# ---- document helpers -----------------------------------------------------


def _address_dict(source: dict | None) -> dict | None:
    if not source:
        return None
    return {
        "addressLine1": source.get("addressLine1") or source.get("line1"),
        "addressLine2": source.get("addressLine2") or source.get("line2"),
        "city": source.get("city"),
        "stateCode": source.get("stateCode"),
        "postalCode": source.get("postalCode"),
        "country": source.get("country"),
    }


def _build_po_document_data(tenant_id, po: PurchaseOrder) -> dict:
    """Shared by the plain "Download PDF" route and the issue/email dispatch
    flow, so both always render from the exact same data."""
    try:
        vendor = party_summary.build_summary_by_id(tenant_id, po.vendor_id)
    except ProblemError:
        vendor = None

    lines = procurement_repo.lines_of(po.id)
    seller = org_repo.resolve_seller(tenant_id, po.business_entity_id)
    warehouse = warehouse_repo.get_warehouse_summary(tenant_id, po.warehouse_id)

    return {
        "number": po.number,
        "revision": po.revision,
        "poDate": po.po_date.isoformat() if po.po_date else None,
        "expectedDate": po.expected_date.isoformat() if po.expected_date else None,
        "seller": seller,
        "vendor": {
            "name": vendor["displayName"] if vendor else po.vendor_name,
            "taxId": vendor.get("taxId") if vendor else None,
            **(_address_dict(vendor.get("billingAddress")) if vendor and vendor.get("billingAddress") else {}),
        },
        "warehouse": po.warehouse_code,
        "deliveryAddress": {"name": warehouse["name"] if warehouse else po.warehouse_code, **(_address_dict(warehouse) or {})} if warehouse else None,
        "currency": po.currency,
        "subtotal": decimal_str(po.subtotal),
        "taxTotal": decimal_str(po.tax_total),
        "cgst": decimal_str(po.cgst),
        "sgst": decimal_str(po.sgst),
        "igst": decimal_str(po.igst),
        "charges": decimal_str(po.charges),
        "total": decimal_str(po.total),
        "paymentTerms": po.payment_terms,
        "paymentMode": po.payment_mode,
        "incoterms": po.incoterms,
        "notes": po.notes,
        "lines": [
            {
                "sku": l.sku,
                "description": l.description or l.sku,
                "quantity": decimal_str(l.quantity),
                "uom": l.uom,
                "unitPrice": decimal_str(l.unit_price),
                "taxRate": decimal_str(l.tax_rate),
                "netAmount": decimal_str(l.net_amount),
                "grossAmount": decimal_str(l.gross_amount),
            }
            for l in lines
        ],
    }


def _dispatch_po(tenant_id, po_id, to: list[str] | None, cc: list[str] | None) -> dict:
    """Rendering and emailing the PO are side effects of issuing, not part of
    it - a failure here never rolls the PO back to a prior status (it stays
    issued, email_state records the failure)."""
    po = procurement_repo.require_po(tenant_id, po_id)
    try:
        vendor = party_summary.build_summary_by_id(tenant_id, po.vendor_id)
    except ProblemError:
        vendor = None
    recipients = to if to else ([vendor["email"]] if vendor and vendor.get("email") else [])

    if not recipients:
        po.email_state = "failed"
        po.email_error = "No vendor email address on file"
        return {"emailState": "failed", "pdfDocumentId": po.pdf_document_id, "error": "No vendor email address on file"}

    document_data = _build_po_document_data(tenant_id, po)

    pdf = document_repo.render_document(tenant_id, template="purchase-order", data=document_data, filename=f"{po.number}.pdf", related_type="purchase-order", related_id=str(po.id))
    po.pdf_document_id = pdf["id"]

    try:
        result = notification_repo.send_notification(
            tenant_id,
            template="purchase-order.issued",
            to=recipients,
            cc=cc or [],
            data={**document_data, "pdfUrl": pdf["url"]},
            related_type="purchase-order",
            related_id=str(po.id),
        )
        po.email_state = notification_repo.delivery_state(result)
        po.email_error = result.get("error")
        if po.email_state == "sent":
            po.email_sent_at = datetime.now(timezone.utc)
    except ProblemError as exc:
        po.email_state = "failed"
        po.email_error = exc.detail

    return {"emailState": po.email_state, "pdfDocumentId": str(po.pdf_document_id), "error": po.email_error}
