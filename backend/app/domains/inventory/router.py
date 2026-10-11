"""Inventory: balances/ledger/valuation views, reservations, adjustments,
status-change, transfers. Ported 1:1 (behavior) from
backend_py/app/routes/inventory_balances.py and the non-production part of
inventory_movements.py (reservations through complete_transfer, i.e. that
file's lines 1-1352). Production (planning/complete/stages, BOM-driven
manufacturing, finished-good item tracking) is ported separately as its own
domain - see app/domains/production/router.py (that file's lines 1355-2660).
"""

from __future__ import annotations

import csv
import io
import uuid as uuid_mod
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import case, func, or_

from app.core.auth import Actor, require_permission
from app.core.access_scope import assert_warehouse_in_scope, scope_query_by_warehouse
from app.core.audit import audit
from app.core.config import settings
from app.core.db import session
from app.core.errors import ProblemError, conflict, not_found, rule_violation
from app.core.idempotency import get_raw_body, run_idempotent
from app.core.money import decimal_str, is_zero, to_decimal
from app.core.pagination import ListQuery, list_response, offset_of
from app.domains.inventory.schemas import (
    AdjustmentBody,
    AdjustmentBulkUploadBody,
    CompleteTransferBody,
    ReleaseBody,
    ReservationBody,
    StatusChangeBody,
    TransferBody,
    TransferBulkUploadBody,
)
from app.models.inventory_item import InventoryItem
from app.models.product import Product
from app.models.reservation import Reservation
from app.models.stock_balance import StockBalance
from app.models.stock_ledger import StockLedger
from app.models.transfer import Transfer
from app.models.warehouse import Warehouse
from app.services import inventory_ledger, product_repo, warehouse_repo
from app.services.availability import assert_sufficient, compute_availability
from app.services.inventory_ledger import LedgerPosting
from app.services.sequences import next_document_number

router = APIRouter(prefix="/api/v1", tags=["inventory"])

_BASE36 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _to_base36(n: int) -> str:
    if n == 0:
        return "0"
    digits = []
    while n:
        n, r = divmod(n, 36)
        digits.append(_BASE36[r])
    return "".join(reversed(digits))


def _timestamp_ref(prefix: str) -> str:
    return f"{prefix}-{_to_base36(int(datetime.now(timezone.utc).timestamp() * 1000))}"


# ============================================================================
# balances / ledger / valuation
# ============================================================================


@router.get("/inventory/balances")
def list_balances(
    actor: Actor = Depends(require_permission("inventory:read")),
    query: ListQuery = Depends(),
    productId: uuid_mod.UUID | None = None,
    warehouseId: uuid_mod.UUID | None = None,
    batchNo: str | None = None,
    bucket: str | None = None,
    includeZero: bool = False,
    expiringWithinDays: int | None = None,
):
    """The inventory grid. One row per (product, warehouse, batch, location)
    with every bucket alongside."""
    tenant_id = actor["tenant_id"]

    cols = [
        StockBalance.product_id,
        StockBalance.sku,
        StockBalance.warehouse_id,
        StockBalance.location_id,
        StockBalance.batch_no,
        func.max(StockBalance.expiry_date).label("expiry_date"),
        func.max(StockBalance.uom).label("uom"),
    ]
    for b in ("available", "quarantine", "damaged", "in_transit", "expired", "reserved"):
        cols.append(func.coalesce(func.sum(case((StockBalance.bucket == b, StockBalance.quantity), else_=0)), 0).label(b))

    q = session.query(*cols).filter(StockBalance.tenant_id == tenant_id)
    if productId:
        q = q.filter(StockBalance.product_id == productId)
    if warehouseId:
        assert_warehouse_in_scope(actor, warehouseId)
        q = q.filter(StockBalance.warehouse_id == warehouseId)
    else:
        q = scope_query_by_warehouse(q, StockBalance.warehouse_id, actor)
    if batchNo:
        q = q.filter(StockBalance.batch_no == batchNo)
    if bucket:
        q = q.filter(StockBalance.bucket == bucket)
    if expiringWithinDays is not None:
        cutoff = date.today() + timedelta(days=expiringWithinDays)
        q = q.filter(StockBalance.expiry_date.isnot(None), StockBalance.expiry_date <= cutoff)
    if query.q:
        q = q.filter(StockBalance.sku.ilike(f"%{query.q}%"))

    q = q.group_by(StockBalance.tenant_id, StockBalance.product_id, StockBalance.sku, StockBalance.warehouse_id, StockBalance.location_id, StockBalance.batch_no)
    if not includeZero:
        total_expr = func.sum(StockBalance.quantity)
        q = q.having(total_expr != 0)

    grouped = q.order_by(StockBalance.sku, StockBalance.batch_no).subquery()
    total = session.query(func.count()).select_from(grouped).scalar() or 0
    rows = q.order_by(StockBalance.sku, StockBalance.batch_no).limit(query.limit).offset(offset_of(query)).all()

    data = []
    for r in rows:
        entry = {
            "productId": str(r.product_id),
            "sku": r.sku,
            "warehouseId": str(r.warehouse_id),
            "locationId": str(r.location_id) if r.location_id else None,
            "batchNo": r.batch_no or None,
            "expiryDate": r.expiry_date.isoformat() if r.expiry_date else None,
            "uom": r.uom,
        }
        entry.update(compute_availability({"available": r.available, "quarantine": r.quarantine, "damaged": r.damaged, "in_transit": r.in_transit, "expired": r.expired, "reserved": r.reserved}))
        data.append(entry)

    return list_response(data, query, total)


@router.get("/inventory/ledger")
def list_ledger(
    actor: Actor = Depends(require_permission("inventory:read")),
    query: ListQuery = Depends(),
    productId: uuid_mod.UUID | None = None,
    warehouseId: uuid_mod.UUID | None = None,
    batchNo: str | None = None,
    movementType: str | None = None,
    referenceId: str | None = None,
    from_: str | None = None,
    to_: str | None = None,
):
    """The append-only movement history - the audit answer to "why is it 9,050?"."""
    tenant_id = actor["tenant_id"]

    q = StockLedger.query.filter(StockLedger.tenant_id == tenant_id)
    if productId:
        q = q.filter(StockLedger.product_id == productId)
    if warehouseId:
        assert_warehouse_in_scope(actor, warehouseId)
        q = q.filter(StockLedger.warehouse_id == warehouseId)
    else:
        q = scope_query_by_warehouse(q, StockLedger.warehouse_id, actor)
    if batchNo:
        q = q.filter(StockLedger.batch_no == batchNo)
    if movementType:
        q = q.filter(StockLedger.movement_type == movementType)
    if referenceId:
        q = q.filter(StockLedger.reference_id == referenceId)
    if from_:
        q = q.filter(StockLedger.created_at >= from_)
    if to_:
        q = q.filter(StockLedger.created_at < (date.fromisoformat(to_) + timedelta(days=1)).isoformat())
    if query.q:
        like = f"%{query.q}%"
        q = q.filter(or_(StockLedger.sku.ilike(like), StockLedger.reference_no.ilike(like)))

    total = q.count()
    rows = q.order_by(StockLedger.seq.desc()).limit(query.limit).offset(offset_of(query)).all()

    return list_response(
        [
            {
                "id": str(r.id),
                "seq": r.seq,
                "productId": str(r.product_id),
                "sku": r.sku,
                "warehouseId": str(r.warehouse_id),
                "locationId": str(r.location_id) if r.location_id else None,
                "batchNo": r.batch_no,
                "quantity": decimal_str(r.quantity),
                "uom": r.uom,
                "bucket": r.bucket,
                "movementType": r.movement_type,
                "referenceType": r.reference_type,
                "referenceId": r.reference_id,
                "referenceNo": r.reference_no,
                "unitCost": decimal_str(r.unit_cost) if r.unit_cost is not None else None,
                "reason": r.reason,
                "actorId": r.actor_id,
                "correlationId": r.correlation_id,
                "at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
        query,
        total,
    )


@router.get("/inventory/valuation")
def valuation(actor: Actor = Depends(require_permission("inventory:read")), warehouseId: uuid_mod.UUID | None = None, bucket: str | None = None):
    tenant_id = actor["tenant_id"]
    warehouse_filter: object = warehouseId
    if warehouseId:
        assert_warehouse_in_scope(actor, warehouseId)
    elif actor["warehouse_ids"] is not None:
        warehouse_filter = actor["warehouse_ids"]
    return inventory_ledger.compute_valuation(tenant_id, warehouse_filter, bucket)


@router.get("/inventory/average-costs")
def average_costs(actor: Actor = Depends(require_permission("inventory:read"))):
    costs = inventory_ledger.average_costs(actor["tenant_id"])
    return {"data": [{"productId": product_id, "averageCost": decimal_str(cost)} for product_id, cost in costs.items()]}


# ============================================================================
# reservations
# ============================================================================


@router.post("/inventory/reservations", status_code=201)
def create_reservation_route(body: ReservationBody, request: Request, raw_body: bytes = Depends(get_raw_body), actor: Actor = Depends(require_permission("inventory:reserve"))):
    tenant_id = actor["tenant_id"]
    assert_warehouse_in_scope(actor, body.warehouseId)

    def _do():
        result = inventory_ledger.create_reservation(
            tenant_id,
            product_id=body.productId,
            warehouse_id=body.warehouseId,
            quantity=body.quantity,
            uom=body.uom,
            batch_no=body.batchNo,
            order_id=body.orderId,
            order_line_id=body.orderLineId,
            reference_type=body.referenceType,
            reference_no=body.referenceNo,
            expires_at=body.expiresAt,
            created_by=str(actor["user_id"]),
        )
        session.commit()
        return 201, result

    status_code, response_body = run_idempotent(request.headers.get("Idempotency-Key"), "POST", request.url.path, raw_body, actor, _do)
    return JSONResponse(status_code=status_code, content=response_body)


@router.post("/inventory/reservations/{id}/release", status_code=204)
def release_reservation_route(id: uuid_mod.UUID, body: ReleaseBody, actor: Actor = Depends(require_permission("inventory:reserve"))):
    from fastapi import Response

    reservation = Reservation.query.filter_by(tenant_id=actor["tenant_id"], id=id).first()
    if not reservation:
        raise not_found("Reservation")
    assert_warehouse_in_scope(actor, reservation.warehouse_id)
    inventory_ledger.release_reservation(actor["tenant_id"], id, body.reason or "Released by user")
    session.commit()
    return Response(status_code=204)


@router.get("/inventory/reservations")
def list_reservations(
    actor: Actor = Depends(require_permission("inventory:read")),
    productId: uuid_mod.UUID | None = None,
    orderId: uuid_mod.UUID | None = None,
    status: str | None = None,
    limit: int = 50,
):
    tenant_id = actor["tenant_id"]
    limit = min(limit, 200)

    q = Reservation.query.filter(Reservation.tenant_id == tenant_id)
    q = scope_query_by_warehouse(q, Reservation.warehouse_id, actor)
    if productId:
        q = q.filter(Reservation.product_id == productId)
    if orderId:
        q = q.filter(Reservation.order_id == orderId)
    if status:
        q = q.filter(Reservation.status == status)
    else:
        q = q.filter(Reservation.status == "open")
    rows = q.order_by(Reservation.created_at.desc()).limit(limit).all()

    return {
        "data": [
            {
                "id": str(r.id),
                "productId": str(r.product_id),
                "sku": r.sku,
                "warehouseId": str(r.warehouse_id),
                "batchNo": r.batch_no,
                "quantity": decimal_str(r.quantity),
                "uom": r.uom,
                "status": r.status,
                "orderId": str(r.order_id) if r.order_id else None,
                "orderLineId": str(r.order_line_id) if r.order_line_id else None,
                "referenceType": r.reference_type,
                "referenceNo": r.reference_no,
                "expiresAt": r.expires_at.isoformat() if r.expires_at else None,
                "createdAt": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    }


# ============================================================================
# adjustments
# ============================================================================


def _create_adjustment(tenant_id, actor: Actor, body: AdjustmentBody) -> dict:
    """Shared by the single-adjustment create route and the bulk-upload route."""
    assert_warehouse_in_scope(actor, body.warehouseId)
    product = product_repo.get_summary(tenant_id, body.productId)
    if not product:
        raise not_found("Product")
    delta = to_decimal(body.quantity)
    if is_zero(delta):
        raise rule_violation("An adjustment of zero has no effect", code="ADJUSTMENT_ZERO")

    item = None
    if body.itemId:
        item = InventoryItem.query.filter_by(tenant_id=tenant_id, id=body.itemId, deleted_at=None).with_for_update().first()
        errors: list[dict] = []
        if not item:
            errors.append({"field": "itemId", "message": "Inventory ID does not exist"})
        else:
            if item.product_id != body.productId:
                errors.append({"field": "itemId", "message": f"{item.inventory_id} is not {product['sku']}"})
            if item.warehouse_id != body.warehouseId:
                errors.append({"field": "itemId", "message": f"{item.inventory_id} is not at the selected warehouse"})
            if item.transfer_id is not None:
                errors.append({"field": "itemId", "message": f"{item.inventory_id} is in transit on a transfer — cannot adjust it"})
            elif item.status != "accepted":
                errors.append({"field": "itemId", "message": f"{item.inventory_id} is {item.status.replace('_', ' ')} — only an accepted item can be adjusted"})
            elif item.bucket != body.bucket:
                errors.append({"field": "itemId", "message": f"{item.inventory_id} is currently {item.bucket}, not {body.bucket}"})
            elif delta < 0:
                item_available = to_decimal(item.accepted_qty) - to_decimal(item.consumed_qty) - to_decimal(item.written_off_qty)
                if abs(delta) > item_available:
                    errors.append({"field": "itemId", "message": f"{item.inventory_id} only has {decimal_str(item_available)} available — cannot write off {decimal_str(abs(delta))}"})
        if errors:
            raise rule_violation(f"Adjustment cannot be created: {'; '.join(e['message'] for e in errors)}", code="ADJUSTMENT_INVALID", meta={"errors": errors})

    inventory_ledger.lock_stock(tenant_id, body.productId, body.warehouseId)

    if delta < 0:
        buckets = inventory_ledger.bucket_totals(tenant_id, body.productId, body.warehouseId)
        in_bucket = to_decimal(buckets.get(body.bucket, "0"))
        if abs(delta) > in_bucket:
            raise rule_violation(
                f"Writing off {decimal_str(abs(delta))} {body.uom} of {product['sku']} would take {body.bucket} stock below zero — "
                f"only {decimal_str(in_bucket)} is on hand",
                code="INSUFFICIENT_STOCK",
            )

    if item is not None:
        if delta < 0:
            item.written_off_qty = to_decimal(item.written_off_qty) + abs(delta)
        else:
            reverse = min(delta, to_decimal(item.written_off_qty))
            item.written_off_qty = to_decimal(item.written_off_qty) - reverse
            remainder = delta - reverse
            if remainder > 0:
                item.accepted_qty = to_decimal(item.accepted_qty) + remainder

    reference = _timestamp_ref("ADJ")
    entry = inventory_ledger.post(
        LedgerPosting(
            tenant_id=tenant_id,
            product_id=body.productId,
            sku=product["sku"],
            warehouse_id=body.warehouseId,
            location_id=body.locationId,
            batch_no=body.batchNo,
            expiry_date=body.expiryDate.isoformat() if body.expiryDate else None,
            quantity=decimal_str(delta),
            uom=body.uom,
            bucket=body.bucket,
            movement_type="adjustment",
            reference_type="adjustment",
            reference_id=reference,
            reference_no=reference,
            unit_cost=body.unitCost,
            currency=settings.base_currency,
            reason=body.reason,
            actor_id=str(actor["user_id"]),
        )
    )

    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="inventory.adjusted", entity_type="inventory", entity_id=str(body.productId), meta={"sku": product["sku"], "quantity": body.quantity, "bucket": body.bucket, "warehouseId": str(body.warehouseId)}, reason=body.reason)
    session.commit()
    return {"reference": reference, "ledgerEntryId": str(entry["id"]) if entry else None}


@router.post("/inventory/adjustments", status_code=201)
def create_adjustment(body: AdjustmentBody, request: Request, raw_body: bytes = Depends(get_raw_body), actor: Actor = Depends(require_permission("inventory:adjust"))):
    tenant_id = actor["tenant_id"]

    def _do():
        return 201, _create_adjustment(tenant_id, actor, body)

    status_code, response_body = run_idempotent(request.headers.get("Idempotency-Key"), "POST", request.url.path, raw_body, actor, _do)
    return JSONResponse(status_code=status_code, content=response_body)


ADJUSTMENT_BULK_UPLOAD_REQUIRED_COLUMNS = ["productSku", "warehouseCode", "quantity", "uom", "reason"]


@router.post("/inventory/adjustments/bulk-upload")
def bulk_upload_adjustments(body: AdjustmentBulkUploadBody, actor: Actor = Depends(require_permission("inventory:adjust"))):
    tenant_id = actor["tenant_id"]

    reader = csv.DictReader(io.StringIO(body.csvContent))
    fieldnames = [(f or "").strip() for f in (reader.fieldnames or [])]
    missing_columns = [c for c in ADJUSTMENT_BULK_UPLOAD_REQUIRED_COLUMNS if c not in fieldnames]
    if missing_columns:
        raise rule_violation(f"CSV is missing required column(s): {', '.join(missing_columns)}", code="BULK_CSV_INVALID_HEADERS")

    results = []
    parsed = [
        (row_number, {(k or "").strip(): (v or "").strip() for k, v in raw_row.items() if k})
        for row_number, raw_row in enumerate(reader, start=2)
    ]
    products_by_sku = product_repo.find_by_skus(tenant_id, [r.get("productSku") or "" for _, r in parsed])
    warehouses_by_code = warehouse_repo.find_warehouses_by_codes(tenant_id, [r.get("warehouseCode") or "" for _, r in parsed])
    locations_by_key = warehouse_repo.find_locations_by_codes(
        [
            (wh.id, r.get("locationCode") or "")
            for _, r in parsed
            if (wh := warehouses_by_code.get((r.get("warehouseCode") or "").upper())) and r.get("locationCode")
        ]
    )

    for row_number, row in parsed:
        if not any(row.values()):
            continue
        errors: list[str] = []

        sku = row.get("productSku") or ""
        product = products_by_sku.get(sku.upper()) if sku else None
        label = product.name if product else (sku or f"(row {row_number})")
        if not sku:
            errors.append("productSku is required")
        elif not product:
            errors.append(f"Product SKU '{sku}' not found")

        warehouse_code = row.get("warehouseCode") or ""
        warehouse = warehouses_by_code.get(warehouse_code.upper()) if warehouse_code else None
        if not warehouse_code:
            errors.append("warehouseCode is required")
        elif not warehouse:
            errors.append(f"Warehouse code '{warehouse_code}' not found")

        location_id = None
        location_code = row.get("locationCode") or ""
        if location_code and warehouse:
            location_row = locations_by_key.get((warehouse.id, location_code.upper()))
            if not location_row:
                errors.append(f"Location code '{location_code}' not found in warehouse {warehouse_code}")
            else:
                location_id = location_row.id

        if errors:
            results.append({"row": row_number, "label": label, "status": "error", "error": "; ".join(errors), "rowData": row})
            continue

        try:
            adjustment_body = AdjustmentBody(
                productId=product.id,
                warehouseId=warehouse.id,
                locationId=location_id,
                batchNo=row.get("batchNo") or None,
                expiryDate=date.fromisoformat(row["expiryDate"]) if row.get("expiryDate") else None,
                quantity=row.get("quantity") or "",
                uom=row.get("uom") or "",
                bucket=row.get("bucket") or "available",
                reason=row.get("reason") or "",
                unitCost=row.get("unitCost") or None,
            )
        except (ValidationError, ValueError) as exc:
            message = exc.errors()[0].get("msg", "invalid data") if isinstance(exc, ValidationError) else str(exc)
            results.append({"row": row_number, "label": label, "status": "error", "error": message, "rowData": row})
            continue

        try:
            result = _create_adjustment(tenant_id, actor, adjustment_body)
            results.append({"row": row_number, "label": label, "status": "success", "reference": result["reference"], "rowData": row})
        except ProblemError as exc:
            session.rollback()
            results.append({"row": row_number, "label": label, "status": "error", "error": exc.detail, "rowData": row})
        except Exception as exc:  # noqa: BLE001 - one bad row must not fail the whole batch
            session.rollback()
            results.append({"row": row_number, "label": label, "status": "error", "error": str(exc), "rowData": row})

    success_count = sum(1 for r in results if r["status"] == "success")
    error_count = len(results) - success_count
    return {
        "summary": {"totalRows": len(results), "successCount": success_count, "errorCount": error_count},
        "results": [
            {
                "row": r["row"],
                "label": r["label"],
                "status": r["status"],
                "reference": r.get("reference"),
                "error": r.get("error"),
                "rowData": r["rowData"] if r["status"] == "error" else {},
            }
            for r in results
        ],
    }


# ============================================================================
# status change
# ============================================================================


def _create_status_change(tenant_id, actor: Actor, body: StatusChangeBody) -> dict:
    assert_warehouse_in_scope(actor, body.warehouseId)
    product = product_repo.get_summary(tenant_id, body.productId)
    if not product:
        raise not_found("Product")

    item = None
    if body.itemId:
        item = InventoryItem.query.filter_by(tenant_id=tenant_id, id=body.itemId, deleted_at=None).with_for_update().first()
        errors: list[dict] = []
        if not item:
            errors.append({"field": "itemId", "message": "Inventory ID does not exist"})
        else:
            if item.product_id != body.productId:
                errors.append({"field": "itemId", "message": f"{item.inventory_id} is not {product['sku']}"})
            if item.warehouse_id != body.warehouseId:
                errors.append({"field": "itemId", "message": f"{item.inventory_id} is not at the selected warehouse"})
            if item.transfer_id is not None:
                errors.append({"field": "itemId", "message": f"{item.inventory_id} is in transit on a transfer — cannot change its status"})
            elif item.status != "accepted":
                errors.append({"field": "itemId", "message": f"{item.inventory_id} is {item.status.replace('_', ' ')} — only an accepted item has a condition bucket to change"})
            elif item.bucket != body.from_:
                errors.append({"field": "itemId", "message": f"{item.inventory_id} is currently {item.bucket}, not {body.from_}"})
            else:
                item_available = to_decimal(item.accepted_qty) - to_decimal(item.consumed_qty) - to_decimal(item.written_off_qty)
                if item_available <= 0:
                    errors.append({"field": "itemId", "message": f"{item.inventory_id} has nothing left available to move"})
                elif to_decimal(body.quantity) != item_available:
                    errors.append({"field": "itemId", "message": f"{item.inventory_id} has {decimal_str(item_available)} available — a specific Inventory ID must be moved in full, not a partial quantity"})
        if errors:
            raise rule_violation(f"Status change cannot be created: {'; '.join(e['message'] for e in errors)}", code="STATUS_CHANGE_INVALID", meta={"errors": errors})

    inventory_ledger.lock_stock(tenant_id, body.productId, body.warehouseId)
    buckets = inventory_ledger.bucket_totals(tenant_id, body.productId, body.warehouseId)
    free = to_decimal(buckets.get(body.from_, "0"))
    if to_decimal(body.quantity) > free:
        raise rule_violation(f"Only {decimal_str(free)} {body.uom} of {product['sku']} is free in {body.from_} — cannot move {body.quantity}", code="INSUFFICIENT_STOCK")

    if item is not None:
        item.bucket = body.to

    reference = _timestamp_ref("STS")
    common = dict(
        tenant_id=tenant_id,
        product_id=body.productId,
        sku=product["sku"],
        warehouse_id=body.warehouseId,
        location_id=body.locationId,
        batch_no=body.batchNo,
        uom=body.uom,
        movement_type="status_change",
        reference_type=f"status:{body.from_}->{body.to}",
        reference_no=reference,
        reason=body.reason,
        actor_id=str(actor["user_id"]),
    )
    inventory_ledger.post(LedgerPosting(reference_id=f"{reference}:out", quantity=decimal_str(-to_decimal(body.quantity)), bucket=body.from_, **common))
    inventory_ledger.post(LedgerPosting(reference_id=f"{reference}:in", quantity=body.quantity, bucket=body.to, **common))

    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="inventory.status-changed", entity_type="inventory", entity_id=str(body.productId), meta={"sku": product["sku"], "quantity": body.quantity, "from": body.from_, "to": body.to}, reason=body.reason)
    session.commit()

    return {"reference": reference, "from": body.from_, "to": body.to, "quantity": body.quantity}


@router.post("/inventory/status-change", status_code=201)
def status_change_route(body: StatusChangeBody, request: Request, raw_body: bytes = Depends(get_raw_body), actor: Actor = Depends(require_permission("inventory:adjust"))):
    tenant_id = actor["tenant_id"]
    if body.from_ == body.to:
        raise rule_violation("Source and destination status are the same", code="STATUS_CHANGE_NOOP")

    def _do():
        return 201, _create_status_change(tenant_id, actor, body)

    status_code, response_body = run_idempotent(request.headers.get("Idempotency-Key"), "POST", request.url.path, raw_body, actor, _do)
    return JSONResponse(status_code=status_code, content=response_body)


# ============================================================================
# transfers
# ============================================================================


def _create_transfer(tenant_id, actor: Actor, body: TransferBody) -> Transfer:
    """Shared by the single-transfer create route and the bulk-upload route."""
    assert_warehouse_in_scope(actor, body.sourceWarehouseId)
    assert_warehouse_in_scope(actor, body.destWarehouseId)
    product = product_repo.get_summary(tenant_id, body.productId)
    source = warehouse_repo.get_warehouse_summary(tenant_id, body.sourceWarehouseId)
    dest = warehouse_repo.get_warehouse_summary(tenant_id, body.destWarehouseId)
    source_loc = warehouse_repo.get_location_summary(tenant_id, body.sourceLocationId) if body.sourceLocationId else None
    dest_loc = warehouse_repo.get_location_summary(tenant_id, body.destLocationId) if body.destLocationId else None

    errors: list[dict] = []
    if not product:
        errors.append({"field": "productId", "message": f"Product {body.productId} does not exist"})
    if not source:
        errors.append({"field": "sourceWarehouseId", "message": "Source warehouse does not exist"})
    elif source["status"] != "active":
        errors.append({"field": "sourceWarehouseId", "message": f"Source warehouse {source['code']} is {source['status']}"})
    if not dest:
        errors.append({"field": "destWarehouseId", "message": "Destination warehouse does not exist"})
    elif dest["status"] != "active":
        errors.append({"field": "destWarehouseId", "message": f"Destination warehouse {dest['code']} is {dest['status']}"})
    if body.sourceLocationId and not source_loc:
        errors.append({"field": "sourceLocationId", "message": "Source location does not exist"})
    if source_loc and source_loc["status"] != "active":
        errors.append({"field": "sourceLocationId", "message": f"Source location {source_loc['code']} is {source_loc['status']}"})
    if body.destLocationId and not dest_loc:
        errors.append({"field": "destLocationId", "message": "Destination location does not exist"})
    if dest_loc and dest_loc["status"] != "active":
        errors.append({"field": "destLocationId", "message": f"Destination location {dest_loc['code']} is {dest_loc['status']}"})
    if body.sourceWarehouseId == body.destWarehouseId and body.sourceLocationId == body.destLocationId:
        errors.append({"field": "destWarehouseId", "message": "Source and destination are the same"})

    item = None
    if body.itemId:
        item = InventoryItem.query.filter_by(tenant_id=tenant_id, id=body.itemId, deleted_at=None).with_for_update().first()
        if not item:
            errors.append({"field": "itemId", "message": "Inventory ID does not exist"})
        else:
            if item.product_id != body.productId:
                errors.append({"field": "itemId", "message": f"{item.inventory_id} is not {product['sku']}" if product else f"{item.inventory_id} does not match the selected SKU"})
            if item.warehouse_id != body.sourceWarehouseId:
                errors.append({"field": "itemId", "message": f"{item.inventory_id} is not at the source warehouse"})
            if item.transfer_id is not None:
                errors.append({"field": "itemId", "message": f"{item.inventory_id} is already in transit on another transfer"})
            elif item.status != "accepted":
                errors.append({"field": "itemId", "message": f"{item.inventory_id} is {item.status.replace('_', ' ')} — only an available item can be transferred"})
            else:
                item_available = to_decimal(item.accepted_qty) - to_decimal(item.consumed_qty) - to_decimal(item.written_off_qty)
                if item_available <= 0:
                    errors.append({"field": "itemId", "message": f"{item.inventory_id} has nothing left available to transfer"})
                elif to_decimal(body.quantity) != item_available:
                    errors.append({"field": "itemId", "message": f"{item.inventory_id} has {decimal_str(item_available)} available — a specific Inventory ID must be transferred in full, not a partial quantity"})

    if errors:
        raise rule_violation(f"Transfer cannot be created: {'; '.join(e['message'] for e in errors)}", code="TRANSFER_INVALID", meta={"errors": errors})

    inventory_ledger.lock_stock(tenant_id, body.productId, body.sourceWarehouseId)
    buckets = inventory_ledger.bucket_totals(tenant_id, body.productId, body.sourceWarehouseId)
    view = compute_availability(buckets)
    assert_sufficient(sku=product["sku"], warehouse_code=source["code"], requested=body.quantity, available_to_promise=view["availableToPromise"], uom=body.uom, batch_no=body.batchNo)

    number = next_document_number(tenant_id, "TRF", pad=4, start=1000)
    transfer = Transfer(
        tenant_id=tenant_id,
        number=number,
        product_id=body.productId,
        sku=product["sku"],
        batch_no=body.batchNo,
        quantity=body.quantity,
        uom=body.uom,
        source_warehouse_id=body.sourceWarehouseId,
        source_location_id=body.sourceLocationId,
        dest_warehouse_id=body.destWarehouseId,
        dest_location_id=body.destLocationId,
        reason=body.reason,
        created_by=str(actor["user_id"]),
    )
    session.add(transfer)
    session.flush()

    if item is not None:
        item.warehouse_id = body.destWarehouseId
        item.location_id = None
        item.location_code = None
        item.transfer_id = transfer.id

    base = dict(tenant_id=tenant_id, product_id=body.productId, sku=product["sku"], batch_no=body.batchNo, uom=body.uom, reference_type="transfer", reference_id=str(transfer.id), reference_no=number, actor_id=str(actor["user_id"]))
    inventory_ledger.post(LedgerPosting(warehouse_id=body.sourceWarehouseId, location_id=body.sourceLocationId, quantity=decimal_str(-to_decimal(body.quantity)), bucket="available", movement_type="transfer_out", **base))
    inventory_ledger.post(LedgerPosting(warehouse_id=body.destWarehouseId, location_id=body.destLocationId, quantity=body.quantity, bucket="in_transit", movement_type="transfer_in", **base))

    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="inventory.transfer.created", entity_type="transfer", entity_id=str(transfer.id), meta={"number": number, "sku": product["sku"], "quantity": body.quantity, "from": source["code"], "to": dest["code"]})
    session.commit()
    return transfer


def _to_transfer_api(row: Transfer, product_name: str | None, source_name: str | None, dest_name: str | None) -> dict:
    return {
        "id": str(row.id),
        "number": row.number,
        "productId": str(row.product_id),
        "sku": row.sku,
        "productName": product_name,
        "batchNo": row.batch_no,
        "quantity": decimal_str(row.quantity),
        "uom": row.uom,
        "sourceWarehouseId": str(row.source_warehouse_id),
        "sourceWarehouseName": source_name,
        "destWarehouseId": str(row.dest_warehouse_id),
        "destWarehouseName": dest_name,
        "status": row.status,
        "dispatchedAt": row.dispatched_at.isoformat() if row.dispatched_at else None,
        "completedAt": row.completed_at.isoformat() if row.completed_at else None,
        "reason": row.reason,
    }


@router.get("/inventory/transfers")
def list_transfers(actor: Actor = Depends(require_permission("inventory:transfer")), query: ListQuery = Depends(), status: str | None = None, warehouseId: uuid_mod.UUID | None = None):
    tenant_id = actor["tenant_id"]

    q = Transfer.query.filter(Transfer.tenant_id == tenant_id)
    if status:
        q = q.filter(Transfer.status == status)
    if warehouseId:
        assert_warehouse_in_scope(actor, warehouseId)
        q = q.filter(or_(Transfer.source_warehouse_id == warehouseId, Transfer.dest_warehouse_id == warehouseId))
    else:
        allowed = actor.get("warehouse_ids")
        if allowed is not None:
            q = q.filter(or_(Transfer.source_warehouse_id.in_(allowed), Transfer.dest_warehouse_id.in_(allowed)))

    total = q.count()
    rows = q.order_by(Transfer.dispatched_at.desc()).limit(query.limit).offset(offset_of(query)).all()

    product_ids = {r.product_id for r in rows}
    warehouse_ids = {r.source_warehouse_id for r in rows} | {r.dest_warehouse_id for r in rows}
    products_by_id = {p.id: p.name for p in Product.query.filter(Product.tenant_id == tenant_id, Product.id.in_(product_ids)).all()} if product_ids else {}
    warehouses_by_id = {w.id: w.name for w in Warehouse.query.filter(Warehouse.tenant_id == tenant_id, Warehouse.id.in_(warehouse_ids)).all()} if warehouse_ids else {}

    data = [_to_transfer_api(r, products_by_id.get(r.product_id), warehouses_by_id.get(r.source_warehouse_id), warehouses_by_id.get(r.dest_warehouse_id)) for r in rows]
    return list_response(data, query, total)


@router.post("/inventory/transfers", status_code=201)
def create_transfer(body: TransferBody, request: Request, raw_body: bytes = Depends(get_raw_body), actor: Actor = Depends(require_permission("inventory:transfer"))):
    tenant_id = actor["tenant_id"]

    def _do():
        transfer = _create_transfer(tenant_id, actor, body)
        return 201, {"id": str(transfer.id), "number": transfer.number, "status": "in_transit"}

    status_code, response_body = run_idempotent(request.headers.get("Idempotency-Key"), "POST", request.url.path, raw_body, actor, _do)
    return JSONResponse(status_code=status_code, content=response_body)


TRANSFER_BULK_UPLOAD_REQUIRED_COLUMNS = ["productSku", "quantity", "uom", "sourceWarehouseCode", "destWarehouseCode"]


@router.post("/inventory/transfers/bulk-upload")
def bulk_upload_transfers(body: TransferBulkUploadBody, actor: Actor = Depends(require_permission("inventory:transfer"))):
    tenant_id = actor["tenant_id"]

    reader = csv.DictReader(io.StringIO(body.csvContent))
    fieldnames = [(f or "").strip() for f in (reader.fieldnames or [])]
    missing_columns = [c for c in TRANSFER_BULK_UPLOAD_REQUIRED_COLUMNS if c not in fieldnames]
    if missing_columns:
        raise rule_violation(f"CSV is missing required column(s): {', '.join(missing_columns)}", code="BULK_CSV_INVALID_HEADERS")

    parsed = [
        (row_number, {(k or "").strip(): (v or "").strip() for k, v in raw_row.items() if k})
        for row_number, raw_row in enumerate(reader, start=2)
    ]
    products_by_sku = product_repo.find_by_skus(tenant_id, [r.get("productSku") or "" for _, r in parsed])
    warehouses_by_code = warehouse_repo.find_warehouses_by_codes(
        tenant_id,
        [r.get("sourceWarehouseCode") or "" for _, r in parsed] + [r.get("destWarehouseCode") or "" for _, r in parsed],
    )
    location_pairs = []
    for _, r in parsed:
        for wh_key, loc_key in (("sourceWarehouseCode", "sourceLocationCode"), ("destWarehouseCode", "destLocationCode")):
            wh = warehouses_by_code.get((r.get(wh_key) or "").upper())
            loc_code = r.get(loc_key) or ""
            if wh and loc_code:
                location_pairs.append((wh.id, loc_code))
    locations_by_key = warehouse_repo.find_locations_by_codes(location_pairs)

    results = []
    for row_number, row in parsed:
        if not any(row.values()):
            continue
        errors: list[str] = []

        sku = row.get("productSku") or ""
        product = products_by_sku.get(sku.upper()) if sku else None
        label = product.name if product else (sku or f"(row {row_number})")
        if not sku:
            errors.append("productSku is required")
        elif not product:
            errors.append(f"Product SKU '{sku}' not found")

        source_wh_code = row.get("sourceWarehouseCode") or ""
        source_wh = warehouses_by_code.get(source_wh_code.upper()) if source_wh_code else None
        if not source_wh_code:
            errors.append("sourceWarehouseCode is required")
        elif not source_wh:
            errors.append(f"Source warehouse code '{source_wh_code}' not found")

        dest_wh_code = row.get("destWarehouseCode") or ""
        dest_wh = warehouses_by_code.get(dest_wh_code.upper()) if dest_wh_code else None
        if not dest_wh_code:
            errors.append("destWarehouseCode is required")
        elif not dest_wh:
            errors.append(f"Destination warehouse code '{dest_wh_code}' not found")

        source_location_id = None
        source_location_code = row.get("sourceLocationCode") or ""
        if source_location_code and source_wh:
            loc = locations_by_key.get((source_wh.id, source_location_code.upper()))
            if not loc:
                errors.append(f"Source location code '{source_location_code}' not found in warehouse {source_wh_code}")
            else:
                source_location_id = loc.id

        dest_location_id = None
        dest_location_code = row.get("destLocationCode") or ""
        if dest_location_code and dest_wh:
            loc = locations_by_key.get((dest_wh.id, dest_location_code.upper()))
            if not loc:
                errors.append(f"Destination location code '{dest_location_code}' not found in warehouse {dest_wh_code}")
            else:
                dest_location_id = loc.id

        if errors:
            results.append({"row": row_number, "label": label, "status": "error", "error": "; ".join(errors), "rowData": row})
            continue

        try:
            transfer_body = TransferBody(
                productId=product.id,
                batchNo=row.get("batchNo") or None,
                quantity=row.get("quantity") or "",
                uom=row.get("uom") or "",
                sourceWarehouseId=source_wh.id,
                sourceLocationId=source_location_id,
                destWarehouseId=dest_wh.id,
                destLocationId=dest_location_id,
                reason=row.get("reason") or None,
            )
        except ValidationError as exc:
            results.append({"row": row_number, "label": label, "status": "error", "error": exc.errors()[0].get("msg", "invalid data"), "rowData": row})
            continue

        try:
            transfer = _create_transfer(tenant_id, actor, transfer_body)
            results.append({"row": row_number, "label": label, "status": "success", "transferNumber": transfer.number, "rowData": row})
        except ProblemError as exc:
            session.rollback()
            results.append({"row": row_number, "label": label, "status": "error", "error": exc.detail, "rowData": row})
        except Exception as exc:  # noqa: BLE001 - one bad row must not fail the whole batch
            session.rollback()
            results.append({"row": row_number, "label": label, "status": "error", "error": str(exc), "rowData": row})

    success_count = sum(1 for r in results if r["status"] == "success")
    error_count = len(results) - success_count
    return {
        "summary": {"totalRows": len(results), "successCount": success_count, "errorCount": error_count},
        "results": [
            {
                "row": r["row"],
                "label": r["label"],
                "status": r["status"],
                "transferNumber": r.get("transferNumber"),
                "error": r.get("error"),
                "rowData": r["rowData"] if r["status"] == "error" else {},
            }
            for r in results
        ],
    }


@router.post("/inventory/transfers/{id}/complete")
def complete_transfer(id: uuid_mod.UUID, body: CompleteTransferBody, actor: Actor = Depends(require_permission("inventory:transfer"))):
    """Completing a transfer converts in-transit stock into available stock."""
    tenant_id = actor["tenant_id"]

    transfer = session.query(Transfer).filter_by(tenant_id=tenant_id, id=id).with_for_update().first()
    if not transfer:
        raise not_found("Transfer")
    if transfer.status != "in_transit":
        raise conflict(f"Transfer {transfer.number} is already {transfer.status}", code="TRANSFER_NOT_IN_TRANSIT")
    assert_warehouse_in_scope(actor, transfer.dest_warehouse_id)

    dest_location = body.destLocationId or transfer.dest_location_id
    base = dict(
        tenant_id=tenant_id,
        product_id=transfer.product_id,
        sku=transfer.sku,
        warehouse_id=transfer.dest_warehouse_id,
        batch_no=transfer.batch_no,
        uom=transfer.uom,
        reference_type="transfer-complete",
        reference_no=transfer.number,
        actor_id=str(actor["user_id"]),
    )
    inventory_ledger.post(LedgerPosting(reference_id=f"{transfer.id}:out", location_id=transfer.dest_location_id, quantity=decimal_str(-to_decimal(transfer.quantity)), bucket="in_transit", movement_type="transfer_in", **base))
    inventory_ledger.post(LedgerPosting(reference_id=f"{transfer.id}:in", location_id=dest_location, quantity=decimal_str(transfer.quantity), bucket="available", movement_type="transfer_in", **base))

    transfer.status = "completed"
    transfer.completed_at = datetime.now(timezone.utc)
    transfer.dest_location_id = dest_location

    item = InventoryItem.query.filter_by(tenant_id=tenant_id, transfer_id=transfer.id).first()
    if item is not None:
        item.transfer_id = None
        item.location_id = dest_location
        dest_loc = warehouse_repo.get_location_summary(tenant_id, dest_location) if dest_location else None
        item.location_code = dest_loc["code"] if dest_loc else None

    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="inventory.transfer.completed", entity_type="transfer", entity_id=str(id), meta={"number": transfer.number})
    session.commit()

    return {"id": str(id), "number": transfer.number, "status": "completed"}
