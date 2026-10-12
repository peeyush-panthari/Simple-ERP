"""Orders domain: the sales-order creation-through-shipment lifecycle.

Ported 1:1 (behavior) from backend_py/app/routes/orders.py: create, list,
get, patch, confirm, cancel, bulk-upload, allocate (both FEFO/FIFO and
manual pick), pack/ship at both line and order level, invoice (+PDF render,
AR posting, email), invoice download, fulfill, manual-logistics override,
invoices list, audit - including the row-locking stock-allocation machinery
in inventory_ledger.py.

PRESERVED QUIRKS (kept exactly as the original, not "fixed" - see each
docstring below for why): `PATCH /orders/:id` accepts but silently ignores
`deliveryAddress`; `to_order_api`'s `warehouseId` renders the literal string
"None" for an order with no warehouse (Order.warehouse_id is nullable and
no longer set - `str(None)`, not a JSON null).
"""

from __future__ import annotations

import csv
import io
import re
import uuid as uuid_mod
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import or_

from app.core.auth import Actor, CurrentActor, require_any_permission, require_permission
from app.core.config import settings
from app.core.db import session
from app.core.errors import ProblemError, conflict, not_found, rule_violation
from app.core.idempotency import get_raw_body, run_idempotent
from app.core.access_scope import assert_warehouse_in_scope
from app.core.audit import audit, read_audit_trail
from app.core.money import decimal_str, to_decimal
from app.core.pagination import ListQuery, list_response, offset_of
from app.domains.orders.schemas import (
    AllocateItemsBody,
    AllocateOrderBody,
    BulkUploadBody,
    CancelBody,
    ConfirmBody,
    FulfillBody,
    InvoiceBody,
    LineBody,
    ManualLogisticsBody,
    OrderBody,
    PackLineBody,
    PatchOrderBody,
    ShipLineBody,
)
from app.core.permissions import permits_all
from app.models.business_entity import BusinessEntity
from app.models.document import Document
from app.models.finished_good_allocation import FinishedGoodAllocation
from app.models.finished_good_item import FinishedGoodItem
from app.models.invoice import Invoice
from app.models.invoice_line import InvoiceLine
from app.models.order import Order
from app.models.order_line import OrderLine
from app.models.reservation import Reservation
from app.services import (
    document_repo,
    document_storage,
    finance_repo,
    inventory_ledger,
    logistics_repo,
    notification_repo,
    order_repo,
    org_repo,
    party_repo,
    party_summary,
    product_repo,
    warehouse_repo,
)
from app.services.finished_good_status import recompute_status
from app.services.order_settlement import assert_invoice_matches_order, assert_logistics_allowed, evaluate_logistics_trigger, settlement_position
from app.services.order_state import assert_allocatable, assert_editable, assert_invoiceable, assert_shippable, assert_transition
from app.services.party_repo import apply_credit_usage_for_party
from app.services.sequences import next_document_number
from app.services.tax_codes import TaxableLine, compute_totals, is_known_tax_code, split_gst

router = APIRouter(prefix="/api/v1", tags=["orders"])

#  Production's Order Shipping tab and Finance's Invoices tab both call these
#  directly - not only the Orders module itself - so both accept
#  inventory:read/finance:read too. Full CRUD stays behind order:write etc.
_ORDER_LOOKUP_PERMISSIONS = ("order:read", "inventory:read", "finance:read")


def _validate_order(tenant_id, body) -> dict:
    """Cross-module validation: vendor/every product checked, all failures
    aggregated into one ORDER_VALIDATION_FAILED report."""
    errors: list[dict] = []
    try:
        customer = party_summary.build_summary_by_id(tenant_id, body.customerId)
    except ProblemError:
        customer = None
    products = product_repo.get_summaries(tenant_id, [l.productId for l in body.lines])

    if not customer:
        errors.append({"field": "customerId", "message": f"Customer {body.customerId} does not exist"})
    else:
        if customer["type"] == "vendor":
            errors.append({"field": "customerId", "message": f"{customer['code']} is a vendor, not a customer"})
        if customer["status"] != "active":
            errors.append({"field": "customerId", "message": f"{customer['code']} is {customer['status']}{' (blocked)' if customer['blocked'] else ''} — only active customers can raise sales orders"})

    order_date = getattr(body, "orderDate", None) or date.today()
    if body.promisedDate < order_date:
        errors.append({"field": "promisedDate", "message": f"Promised date ({body.promisedDate.isoformat()}) cannot be before the order date ({order_date.isoformat()})"})

    resolved_lines = []
    for i, line in enumerate(body.lines):
        product = products.get(str(line.productId))
        field = f"lines.{i}"
        if not product:
            errors.append({"field": field, "message": f"Product {line.productId} does not exist"})
            resolved_lines.append({"line": line, "product": None, "taxCode": line.taxCode or "GST18"})
            continue
        if product["status"] != "active":
            errors.append({"field": field, "message": f"{product['sku']} is {product['status']} and cannot be sold"})
        if not product.get("sellable", True):
            errors.append({"field": field, "message": f"{product['sku']} is not flagged sellable"})
        tax_code = line.taxCode or "GST18"
        if not is_known_tax_code(tax_code):
            errors.append({"field": f"{field}.taxCode", "message": f'"{tax_code}" is not a configured tax code'})
        resolved_lines.append({"line": line, "product": product, "taxCode": tax_code})

    if errors:
        raise rule_violation(f"The sales order has {len(errors)} problem{'s' if len(errors) > 1 else ''}: {'; '.join(e['message'] for e in errors)}", code="ORDER_VALIDATION_FAILED", meta={"errors": errors})

    totals = compute_totals([TaxableLine(quantity=r["line"].quantity, unit_price=r["line"].unitPrice, tax_code=r["taxCode"], discount=r["line"].discount) for r in resolved_lines], body.charges)

    if getattr(body, "expectedTotal", None) and to_decimal(body.expectedTotal) != to_decimal(totals.total):
        raise rule_violation(
            f"Total mismatch: the server computed {decimal_str(totals.total)} but the request declared {decimal_str(body.expectedTotal)}. Refresh the page — a price or tax code has changed",
            code="TOTAL_MISMATCH",
            meta={"computed": totals.total, "declared": body.expectedTotal},
        )

    return {"customer": customer, "currency": getattr(body, "currency", None) or (customer.get("currency") if customer else None) or settings.base_currency, "totals": totals, "resolvedLines": resolved_lines}


def _insert_lines(tenant_id, order_id, lines: list[LineBody], validated: dict) -> None:
    for i, line in enumerate(lines):
        computed = validated["totals"].lines[i]
        resolved = validated["resolvedLines"][i]
        sku = resolved["product"]["sku"] if resolved["product"] else ""
        session.add(
            OrderLine(
                tenant_id=tenant_id,
                order_id=order_id,
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
                status="open",
            )
        )


def _line_to_input(line: OrderLine) -> LineBody:
    return LineBody(productId=line.product_id, description=line.description, quantity=line.quantity, uom=line.uom, unitPrice=line.unit_price, discount=line.discount, taxCode=line.tax_code)


@router.get("/orders")
def list_orders(
    actor: Actor = Depends(require_any_permission(*_ORDER_LOOKUP_PERMISSIONS)),
    query: ListQuery = Depends(),
    status: str | None = None,
    customerId: uuid_mod.UUID | None = None,
    warehouseId: uuid_mod.UUID | None = None,
    logisticsState: str | None = None,
    from_: str | None = None,
    to_: str | None = None,
    includeLines: bool = False,
):
    tenant_id = actor["tenant_id"]

    q = Order.query.filter(Order.tenant_id == tenant_id)
    if status:
        statuses = [s.strip() for s in status.split(",") if s.strip()]
        if statuses:
            q = q.filter(Order.status.in_(statuses))
    if customerId:
        q = q.filter(Order.customer_id == customerId)
    if warehouseId:
        assert_warehouse_in_scope(actor, warehouseId)
        allocated_order_ids = (
            session.query(OrderLine.order_id)
            .join(Reservation, Reservation.id == OrderLine.reservation_id)
            .filter(Reservation.tenant_id == tenant_id, Reservation.warehouse_id == warehouseId)
        )
        q = q.filter(Order.id.in_(allocated_order_ids))
    elif actor["warehouse_ids"] is not None:
        allocated_order_ids = (
            session.query(OrderLine.order_id)
            .join(Reservation, Reservation.id == OrderLine.reservation_id)
            .filter(Reservation.tenant_id == tenant_id, Reservation.warehouse_id.in_(actor["warehouse_ids"]))
        )
        q = q.filter(Order.id.in_(allocated_order_ids))
    if logisticsState:
        q = q.filter(Order.logistics_state == logisticsState)
    if from_:
        q = q.filter(Order.order_date >= from_)
    if to_:
        q = q.filter(Order.order_date <= to_)
    if query.q:
        like = f"%{query.q}%"
        q = q.filter(or_(Order.number.ilike(like), Order.customer_name.ilike(like)))

    total = q.count()
    sort = (query.sort or "").lstrip("-")
    sortable = {"number": Order.number, "order_date": Order.order_date, "promised_date": Order.promised_date, "total": Order.total, "status": Order.status}
    column = sortable.get(sort, Order.order_date)
    order_by = column.desc() if (query.sort or "").startswith("-") or not query.sort else column.asc()
    rows = q.order_by(order_by).limit(query.limit).offset(offset_of(query)).all()

    lines_by_order: dict[uuid_mod.UUID, list[OrderLine]] = {r.id: [] for r in rows}
    if includeLines and rows:
        order_ids = [r.id for r in rows]
        all_lines = OrderLine.query.filter(OrderLine.order_id.in_(order_ids)).order_by(OrderLine.line_no).all()
        for l in all_lines:
            lines_by_order[l.order_id].append(l)

    return list_response(
        [order_repo.to_order_api(r, lines_by_order[r.id] if includeLines else None) for r in rows],
        query,
        total,
    )


@router.get("/orders/{id}")
def get_order(id: uuid_mod.UUID, actor: Actor = Depends(require_any_permission(*_ORDER_LOOKUP_PERMISSIONS))):
    tenant_id = actor["tenant_id"]
    order = order_repo.require_order(tenant_id, id)
    return order_repo.to_order_api(order, order_repo.lines_of(id))


def _create_order(tenant_id, actor: Actor, body: OrderBody) -> Order:
    """Shared by the single-order create route and the bulk-upload route."""
    if body.promisedDate is None:
        body.promisedDate = (body.orderDate or date.today()) + timedelta(days=7)

    validated = _validate_order(tenant_id, body)
    customer = validated["customer"]
    address = body.deliveryAddress or customer.get("shippingAddress") or customer.get("billingAddress")
    if not address:
        raise rule_violation(f"{customer['code']} has no shipping or billing address on file — add one before ordering", code="DELIVERY_ADDRESS_MISSING")
    address = address if isinstance(address, dict) else address.model_dump()

    from app.services.sequences import next_document_number

    number = next_document_number(tenant_id, settings.so_number_prefix, pad=4, start=7700)
    order = Order(
        tenant_id=tenant_id,
        number=number,
        customer_id=body.customerId,
        customer_name=customer["displayName"],
        customer_ref=body.customerRef,
        status="confirmed",
        order_date=body.orderDate or date.today(),
        promised_date=body.promisedDate,
        currency=validated["currency"],
        subtotal=validated["totals"].subtotal,
        tax_total=validated["totals"].tax_total,
        charges=body.charges,
        total=validated["totals"].total,
        payment_terms=body.paymentTerms or customer.get("paymentTerms"),
        delivery_line1=address["line1"],
        delivery_line2=address.get("line2"),
        delivery_city=address["city"],
        delivery_state_code=address.get("stateCode"),
        delivery_postal_code=address.get("postalCode"),
        delivery_country=address.get("country") or "IN",
        notes=body.notes,
        inverter_details=body.inverterDetails,
        accessories_required=body.accessoriesRequired,
        branding=body.branding,
        logistics_cost_borne_by=body.logisticsCostBorneBy,
        created_by=str(actor["user_id"]),
    )
    session.add(order)
    session.flush()
    _insert_lines(tenant_id, order.id, body.lines, validated)

    if body.inverterDetailsContentBase64:
        document_repo.upload_document(
            tenant_id,
            filename=body.inverterDetailsFilename or f"{number}-inverter-details",
            content_type=body.inverterDetailsContentType or "application/pdf",
            content_base64=body.inverterDetailsContentBase64,
            related_type="order",
            related_id=str(order.id),
            created_by=str(actor["user_id"]),
        )

    apply_credit_usage_for_party(tenant_id, order.customer_id, delta=order.total, reference=number, allow_override=body.allowCreditOverride)

    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="order.created", entity_type="order", entity_id=str(order.id), meta={"number": number, "customer": validated["customer"]["displayName"], "total": validated["totals"].total})
    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="order.confirmed", entity_type="order", entity_id=str(order.id), meta={"total": decimal_str(order.total), "creditOverride": body.allowCreditOverride})
    session.commit()
    return order


@router.post("/orders", status_code=201)
def create_order(
    body: OrderBody,
    request: Request,
    raw_body: bytes = Depends(get_raw_body),
    actor: Actor = Depends(require_permission("order:write")),
):
    tenant_id = actor["tenant_id"]

    def _do():
        order = _create_order(tenant_id, actor, body)
        return 201, order_repo.to_order_api(order_repo.require_order(tenant_id, order.id), order_repo.lines_of(order.id))

    status_code, response_body = run_idempotent(
        request.headers.get("Idempotency-Key"), "POST", request.url.path, raw_body, actor, _do
    )
    return JSONResponse(status_code=status_code, content=response_body)


BULK_UPLOAD_REQUIRED_COLUMNS = ["soRef", "customerCode", "promisedDate", "productSku", "quantity", "unitPrice"]


@router.post("/orders/bulk-upload")
def bulk_upload_orders(body: BulkUploadBody, actor: Actor = Depends(require_permission("order:write"))):
    """Creates many sales orders from one CSV in a single request. Each soRef
    group is independent - one bad group is reported as an error and
    skipped, it never fails groups that already validated fine."""
    tenant_id = actor["tenant_id"]

    reader = csv.DictReader(io.StringIO(body.csvContent))
    fieldnames = [(f or "").strip() for f in (reader.fieldnames or [])]
    missing_columns = [c for c in BULK_UPLOAD_REQUIRED_COLUMNS if c not in fieldnames]
    if missing_columns:
        raise rule_violation(f"CSV is missing required column(s): {', '.join(missing_columns)}", code="BULK_CSV_INVALID_HEADERS")

    groups: dict[str, list[dict]] = {}
    order_refs: list[str] = []
    for row_number, raw_row in enumerate(reader, start=2):
        row = {(k or "").strip(): (v or "").strip() for k, v in raw_row.items() if k}
        row["_rowNumber"] = row_number
        ref = row.get("soRef") or ""
        if not ref:
            continue
        if ref not in groups:
            groups[ref] = []
            order_refs.append(ref)
        groups[ref].append(row)

    customers_by_code = party_repo.find_parties_by_codes(tenant_id, [groups[r][0].get("customerCode") or "" for r in order_refs])
    products_by_sku = product_repo.find_by_skus(tenant_id, [r.get("productSku") or "" for ref in order_refs for r in groups[ref]])

    results = []
    for so_ref in order_refs:
        rows = groups[so_ref]
        first = rows[0]
        errors: list[str] = []

        customer_code = first.get("customerCode") or ""
        customer = customers_by_code.get(customer_code.upper()) if customer_code else None
        if not customer_code:
            errors.append("customerCode is required")
        elif not customer:
            errors.append(f"Customer code '{customer_code}' not found")

        promised_date_raw = first.get("promisedDate") or ""
        promised_date = None
        try:
            promised_date = date.fromisoformat(promised_date_raw)
        except ValueError:
            errors.append(f"Invalid promisedDate '{promised_date_raw}' — use YYYY-MM-DD")

        delivery_address = None
        if first.get("deliveryLine1"):
            delivery_address = {
                "line1": first["deliveryLine1"],
                "city": first.get("deliveryCity") or "",
                "stateCode": first.get("deliveryStateCode") or None,
                "postalCode": first.get("deliveryPostalCode") or None,
                "country": "IN",
            }

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
            results.append({"soRef": so_ref, "status": "error", "error": "; ".join(errors), "rows": rows})
            continue

        try:
            order_body = OrderBody(
                customerId=customer.id,
                customerRef=first.get("customerRef") or None,
                promisedDate=promised_date,
                paymentTerms=first.get("paymentTerms") or None,
                deliveryAddress=delivery_address,
                lines=lines,
            )
        except ValidationError as exc:
            results.append({"soRef": so_ref, "status": "error", "error": exc.errors()[0].get("msg", "invalid order data"), "rows": rows})
            continue

        try:
            order = _create_order(tenant_id, actor, order_body)
            results.append({"soRef": so_ref, "status": "success", "orderNumber": order.number, "rows": rows})
        except ProblemError as exc:
            session.rollback()
            results.append({"soRef": so_ref, "status": "error", "error": exc.detail, "rows": rows})
        except Exception as exc:  # noqa: BLE001 - one bad group must not fail the whole batch
            session.rollback()
            results.append({"soRef": so_ref, "status": "error", "error": str(exc), "rows": rows})

    success_count = sum(1 for r in results if r["status"] == "success")
    error_count = len(results) - success_count
    return {
        "summary": {"totalGroups": len(results), "successCount": success_count, "errorCount": error_count},
        "results": [
            {
                "soRef": r["soRef"],
                "status": r["status"],
                "orderNumber": r.get("orderNumber"),
                "error": r.get("error"),
                "rows": [{k: v for k, v in row.items() if k != "_rowNumber"} for row in r["rows"]] if r["status"] == "error" else [],
            }
            for r in results
        ],
    }


@router.patch("/orders/{id}")
def patch_order(id: uuid_mod.UUID, body: PatchOrderBody, actor: Actor = Depends(require_permission("order:write"))):
    tenant_id = actor["tenant_id"]
    order = order_repo.require_order(tenant_id, id)
    assert_editable(order.number, order.status)

    class _Merged:
        pass

    merged = _Merged()
    merged.customerId = body.customerId or order.customer_id
    merged.promisedDate = body.promisedDate or order.promised_date
    merged.orderDate = order.order_date
    merged.currency = order.currency
    merged.charges = body.charges if body.charges is not None else decimal_str(order.charges)
    merged.lines = body.lines if body.lines is not None else [_line_to_input(l) for l in order_repo.lines_of(id)]
    merged.expectedTotal = body.expectedTotal

    validated = _validate_order(tenant_id, merged)

    order.customer_id = merged.customerId
    order.customer_name = validated["customer"]["displayName"]
    if "customerRef" in body.model_fields_set:
        order.customer_ref = body.customerRef
    order.promised_date = merged.promisedDate
    order.subtotal = validated["totals"].subtotal
    order.tax_total = validated["totals"].tax_total
    order.charges = merged.charges
    order.total = validated["totals"].total
    if body.paymentTerms is not None:
        order.payment_terms = body.paymentTerms
    if "notes" in body.model_fields_set:
        order.notes = body.notes
    if "inverterDetails" in body.model_fields_set:
        order.inverter_details = body.inverterDetails
    if "accessoriesRequired" in body.model_fields_set:
        order.accessories_required = body.accessoriesRequired
    if "branding" in body.model_fields_set:
        order.branding = body.branding
    if "logisticsCostBorneBy" in body.model_fields_set:
        order.logistics_cost_borne_by = body.logisticsCostBorneBy

    if body.lines is not None:
        OrderLine.query.filter_by(order_id=id).delete()
        session.flush()
        _insert_lines(tenant_id, id, body.lines, validated)

    if body.inverterDetailsContentBase64:
        document_repo.upload_document(
            tenant_id,
            filename=body.inverterDetailsFilename or f"{order.number}-inverter-details",
            content_type=body.inverterDetailsContentType or "application/pdf",
            content_base64=body.inverterDetailsContentBase64,
            related_type="order",
            related_id=str(order.id),
            created_by=str(actor["user_id"]),
        )

    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="order.updated", entity_type="order", entity_id=str(id))
    session.commit()

    return order_repo.to_order_api(order_repo.require_order(tenant_id, id), order_repo.lines_of(id))


@router.post("/orders/{id}/confirm")
def confirm_order(id: uuid_mod.UUID, body: ConfirmBody, actor: Actor = Depends(require_permission("order:confirm"))):
    tenant_id = actor["tenant_id"]
    order = order_repo.require_order(tenant_id, id)
    assert_transition(order.number, order.status, "confirmed")

    try:
        customer = party_summary.build_summary_by_id(tenant_id, order.customer_id)
    except ProblemError:
        customer = None
    if not customer or customer["status"] != "active":
        raise rule_violation(f"{order.number}'s customer is no longer active — resolve this before confirming", code="CUSTOMER_NOT_ACTIVE")

    apply_credit_usage_for_party(tenant_id, order.customer_id, delta=order.total, reference=order.number, allow_override=body.allowCreditOverride)

    order.status = "confirmed"
    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="order.confirmed", entity_type="order", entity_id=str(id), meta={"total": decimal_str(order.total), "creditOverride": body.allowCreditOverride})
    session.commit()

    return order_repo.to_order_api(order_repo.require_order(tenant_id, id), order_repo.lines_of(id))


@router.post("/orders/{id}/allocate")
def allocate_order(id: uuid_mod.UUID, body: AllocateOrderBody, actor: Actor = Depends(require_permission("order:allocate"))):
    tenant_id = actor["tenant_id"]
    order = order_repo.require_order(tenant_id, id)
    assert_warehouse_in_scope(actor, body.warehouseId)
    assert_allocatable(order.number, order.status)
    lines = order_repo.lines_of(id)
    non_cancelled = [l for l in lines if l.status != "cancelled"]
    pending = [l for l in non_cancelled if not l.reservation_id]
    if not pending:
        raise rule_violation(f"{order.number} is already fully allocated", code="ORDER_ALREADY_ALLOCATED")

    reservations = []
    failures = []
    for line in pending:
        try:
            result = inventory_ledger.create_reservation(
                tenant_id,
                product_id=line.product_id,
                warehouse_id=body.warehouseId,
                quantity=line.quantity,
                uom=line.uom,
                order_id=order.id,
                order_line_id=line.id,
                reference_type="order",
                reference_no=order.number,
                created_by=str(actor["user_id"]),
            )
        except ProblemError as exc:
            failures.append({"lineId": str(line.id), "sku": line.sku, "reason": exc.detail})
            continue
        line.reservation_id = uuid_mod.UUID(result["reservationId"])
        line.allocated_qty = line.quantity
        line.status = "allocated"
        reservations.append({"lineId": str(line.id), "reservationId": result["reservationId"]})

    if not reservations:
        reason = failures[0]["reason"] if failures else "insufficient stock"
        raise rule_violation(f"{order.number} could not be allocated: {reason}", code="ORDER_ALLOCATION_FAILED", meta={"failures": failures})

    order.status = "allocated" if all(l.reservation_id for l in non_cancelled) else "partially_allocated"
    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="order.allocated", entity_type="order", entity_id=str(id), meta={"reservations": reservations, "failures": failures, "status": order.status})
    session.commit()

    return order_repo.to_order_api(order_repo.require_order(tenant_id, id), order_repo.lines_of(id))


def _recompute_order_allocation_status(order: Order, lines: list[OrderLine]) -> None:
    non_cancelled = [l for l in lines if l.status != "cancelled"]
    if not non_cancelled:
        return
    if all(l.status == "allocated" for l in non_cancelled):
        order.status = "allocated"
    elif any(l.status == "allocated" or l.reservation_id for l in non_cancelled):
        order.status = "partially_allocated"
    else:
        order.status = "confirmed"


@router.post("/orders/{id}/allocate-items")
def allocate_order_items(id: uuid_mod.UUID, body: AllocateItemsBody, actor: Actor = Depends(require_permission("order:allocate"))):
    """Manual counterpart to allocate_order: the operator picks specific
    FinishedGoodItem(s) for one order line instead of letting FEFO/FIFO pick
    a batch by quantity alone."""
    tenant_id = actor["tenant_id"]
    order = order_repo.require_order(tenant_id, id)
    assert_allocatable(order.number, order.status)

    line = OrderLine.query.filter_by(tenant_id=tenant_id, id=body.orderLineId, order_id=order.id).first()
    if not line:
        raise not_found("Order line")
    if line.status == "cancelled":
        raise rule_violation(f"{order.number}'s line {line.sku} is cancelled and cannot be allocated", code="ORDER_LINE_CANCELLED")

    product = product_repo.get_summary(tenant_id, line.product_id)
    if not product or product["type"] != "finished_good":
        raise rule_violation(f"{line.sku} is not a finished good — only finished-good lines can be allocated from Finished Good stock", code="NOT_A_FINISHED_GOOD")

    remaining_on_line = to_decimal(line.quantity) - to_decimal(line.allocated_qty)
    picks: list[tuple[FinishedGoodItem, Decimal]] = []
    errors: list[str] = []
    total_pick = to_decimal(0)
    
    pick_ids = [pick.itemId for pick in body.items]
    items_map = {}
    if pick_ids:
        items = FinishedGoodItem.query.filter(
            FinishedGoodItem.tenant_id == tenant_id,
            FinishedGoodItem.id.in_(pick_ids)
        ).with_for_update().all()
        items_map = {item.id: item for item in items}

    for pick in body.items:
        item = items_map.get(pick.itemId)
        if not item:
            errors.append(f"{pick.itemId} does not exist")
            continue
        if item.product_id != line.product_id:
            errors.append(f"{item.inventory_id} is not {line.sku}")
            continue
        if item.status not in ("available", "partially_reserved"):
            errors.append(f"{item.inventory_id} is {item.status}, not available")
            continue
        free = to_decimal(item.quantity) - to_decimal(item.allocated_qty)
        take = to_decimal(pick.quantity)
        if take <= 0 or take > free:
            errors.append(f"{item.inventory_id}: only {decimal_str(free)} free, cannot allocate {decimal_str(take)}")
            continue
        picks.append((item, take))
        total_pick += take
    if errors:
        raise rule_violation(f"Allocation is invalid: {'; '.join(errors)}", code="ALLOCATION_INVALID", meta={"errors": errors})
    if total_pick > remaining_on_line:
        raise rule_violation(f"{line.sku}: picked {decimal_str(total_pick)} but the line only needs {decimal_str(remaining_on_line)} more", code="ALLOCATION_EXCEEDS_LINE")

    picked_warehouse_ids = {item.warehouse_id for item, _ in picks}
    if len(picked_warehouse_ids) > 1:
        session.rollback()
        raise rule_violation("All picked items must be from the same warehouse — submit separate allocations per warehouse", code="ALLOCATION_MULTIPLE_WAREHOUSES")
    picked_warehouse_id = next(iter(picked_warehouse_ids))
    assert_warehouse_in_scope(actor, picked_warehouse_id)

    reservation = None
    if line.reservation_id:
        reservation = Reservation.query.filter_by(tenant_id=tenant_id, id=line.reservation_id, status="open").with_for_update().first()
    if reservation:
        if reservation.warehouse_id != picked_warehouse_id:
            session.rollback()
            raise rule_violation(f"{line.sku} already has stock allocated from a different warehouse — remove that allocation before picking from another warehouse", code="ALLOCATION_WAREHOUSE_MISMATCH")
        reservation.quantity = decimal_str(to_decimal(reservation.quantity) + total_pick)
    else:
        reservation = Reservation(
            tenant_id=tenant_id,
            product_id=line.product_id,
            sku=line.sku,
            warehouse_id=picked_warehouse_id,
            quantity=decimal_str(total_pick),
            uom=line.uom,
            status="open",
            order_id=order.id,
            order_line_id=line.id,
            reference_type="order",
            reference_no=order.number,
            created_by=str(actor["user_id"]),
        )
        session.add(reservation)
        session.flush()
        line.reservation_id = reservation.id

    for warehouse_id in {item.warehouse_id for item, _ in picks}:
        inventory_ledger.lock_stock(tenant_id, line.product_id, warehouse_id)

    for item, take in picks:
        fg_alloc = FinishedGoodAllocation(tenant_id=tenant_id, reservation_id=reservation.id, finished_good_item_id=item.id, quantity=decimal_str(take))
        session.add(fg_alloc)
        session.flush()
        inventory_ledger.move_bucket(
            tenant_id,
            product_id=item.product_id,
            sku=item.sku,
            warehouse_id=item.warehouse_id,
            location_id=item.location_id,
            batch_no=item.batch_no,
            uom=item.uom or line.uom,
            quantity=take,
            from_bucket="available",
            to_bucket="reserved",
            reference_type="reservation-hold",
            reference_id=str(fg_alloc.id),
            reference_no=order.number,
            reason=f"Allocated to {order.number}",
        )
        item.allocated_qty = to_decimal(item.allocated_qty) + take
        item.allocated_order_id = order.id
        item.allocated_order_number = order.number
        recompute_status(item)

    line.allocated_qty = to_decimal(line.allocated_qty) + total_pick
    if to_decimal(line.allocated_qty) >= to_decimal(line.quantity):
        line.status = "allocated"

    lines = order_repo.lines_of(id)
    _recompute_order_allocation_status(order, lines)
    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="order.items_allocated", entity_type="order", entity_id=str(id), meta={"lineId": str(line.id), "items": [{"itemId": str(i.id), "quantity": decimal_str(q)} for i, q in picks], "status": order.status})
    session.commit()

    return order_repo.to_order_api(order_repo.require_order(tenant_id, id), order_repo.lines_of(id))


@router.get("/orders/lines/{line_id}/allocations")
def list_order_line_allocations(line_id: uuid_mod.UUID, actor: Actor = Depends(require_permission("order:read"))):
    tenant_id = actor["tenant_id"]
    line = OrderLine.query.filter_by(tenant_id=tenant_id, id=line_id).first()
    if not line:
        raise not_found("Order line")
    if not line.reservation_id:
        return []

    rows = FinishedGoodAllocation.query.filter_by(tenant_id=tenant_id, reservation_id=line.reservation_id).all()
    
    item_ids = [row.finished_good_item_id for row in rows if row.finished_good_item_id]
    items_map = {}
    if item_ids:
        items = FinishedGoodItem.query.filter(
            FinishedGoodItem.tenant_id == tenant_id,
            FinishedGoodItem.id.in_(item_ids)
        ).all()
        items_map = {item.id: item for item in items}
        
    result = []
    for row in rows:
        item = items_map.get(row.finished_good_item_id) if row.finished_good_item_id else None
        result.append({"allocationId": str(row.id), "itemId": str(row.finished_good_item_id) if row.finished_good_item_id else None, "inventoryId": item.inventory_id if item else None, "quantity": decimal_str(row.quantity), "uom": line.uom})
    return result


def _recompute_order_packing_status(order: Order, lines: list[OrderLine]) -> None:
    packable = [l for l in lines if l.status != "cancelled" and to_decimal(l.allocated_qty) > 0]
    if packable and all(to_decimal(l.packed_qty) >= to_decimal(l.allocated_qty) for l in packable):
        order.packing_status = "packed"
    else:
        order.packing_status = "pending_packing"


@router.delete("/orders/allocations/{allocation_id}")
def remove_order_allocation(allocation_id: uuid_mod.UUID, actor: Actor = Depends(require_permission("order:allocate"))):
    tenant_id = actor["tenant_id"]
    alloc = FinishedGoodAllocation.query.filter_by(tenant_id=tenant_id, id=allocation_id).first()
    if not alloc:
        raise not_found("Allocation")
    reservation = Reservation.query.filter_by(tenant_id=tenant_id, id=alloc.reservation_id).with_for_update().first()
    if not reservation or reservation.status != "open":
        raise rule_violation("This allocation's reservation is no longer open and cannot be changed", code="RESERVATION_NOT_OPEN")
    if to_decimal(reservation.issued_qty) > 0:
        raise rule_violation("Part of this reservation has already shipped, so this pick can no longer be removed", code="RESERVATION_PARTIALLY_ISSUED")
    assert_warehouse_in_scope(actor, reservation.warehouse_id)

    order = order_repo.require_order(tenant_id, reservation.order_id) if reservation.order_id else None
    line = OrderLine.query.filter_by(tenant_id=tenant_id, id=reservation.order_line_id).first() if reservation.order_line_id else None

    if alloc.finished_good_item_id:
        item = FinishedGoodItem.query.filter_by(tenant_id=tenant_id, id=alloc.finished_good_item_id).with_for_update().first()
        if item:
            inventory_ledger.lock_stock(tenant_id, item.product_id, item.warehouse_id)
            inventory_ledger.move_bucket(
                tenant_id,
                product_id=item.product_id,
                sku=item.sku,
                warehouse_id=item.warehouse_id,
                location_id=item.location_id,
                batch_no=item.batch_no,
                uom=item.uom or reservation.uom,
                quantity=alloc.quantity,
                from_bucket="reserved",
                to_bucket="available",
                reference_type="reservation-release",
                reference_id=str(alloc.id),
                reference_no=reservation.reference_no,
                reason="Finished Good allocation removed",
            )
            item.allocated_qty = to_decimal(item.allocated_qty) - to_decimal(alloc.quantity)
            if order and item.allocated_order_id == order.id:
                item.allocated_order_id = None
                item.allocated_order_number = None
            recompute_status(item)

    if line:
        line.allocated_qty = to_decimal(line.allocated_qty) - to_decimal(alloc.quantity)
        line.packed_qty = min(to_decimal(line.packed_qty), line.allocated_qty)
        if line.status == "allocated":
            line.status = "open"

    other_allocations = FinishedGoodAllocation.query.filter(FinishedGoodAllocation.reservation_id == reservation.id, FinishedGoodAllocation.id != alloc.id).count()
    remaining_qty = to_decimal(reservation.quantity) - to_decimal(alloc.quantity)
    session.delete(alloc)
    if other_allocations and remaining_qty > 0:
        reservation.quantity = decimal_str(remaining_qty)
    else:
        reservation.status = "released"
        reservation.released_at = datetime.now(timezone.utc)
        reservation.released_reason = "Finished Good allocation removed"
        if line:
            line.reservation_id = None

    if order:
        lines = order_repo.lines_of(order.id)
        _recompute_order_allocation_status(order, lines)
        _recompute_order_packing_status(order, lines)

    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="order.item_allocation_removed", entity_type="order", entity_id=str(order.id) if order else None, meta={"allocationId": str(allocation_id), "itemId": str(alloc.finished_good_item_id) if alloc.finished_good_item_id else None})
    session.commit()

    if order:
        return order_repo.to_order_api(order_repo.require_order(tenant_id, order.id), order_repo.lines_of(order.id))
    return {"ok": True}


def _recompute_order_shipping_status(order: Order, lines: list[OrderLine]) -> None:
    non_cancelled = [l for l in lines if l.status != "cancelled"]
    if not non_cancelled:
        return
    if all(l.status == "shipped" for l in non_cancelled):
        order.status = "shipped"
        order.shipped_at = datetime.now(timezone.utc)
    elif any(to_decimal(l.shipped_qty) > 0 for l in non_cancelled):
        order.status = "partially_shipped"


@router.post("/orders/lines/{line_id}/pack")
def pack_order_line(line_id: uuid_mod.UUID, body: PackLineBody, actor: Actor = Depends(require_permission("order:pack"))):
    tenant_id = actor["tenant_id"]
    line = OrderLine.query.filter_by(tenant_id=tenant_id, id=line_id).first()
    if not line:
        raise not_found("Order line")
    if line.status == "cancelled":
        raise rule_violation(f"{line.sku} is cancelled and cannot be packed", code="LINE_CANCELLED")
    if line.status == "shipped":
        raise rule_violation(f"{line.sku} has already shipped and cannot be packed", code="LINE_ALREADY_SHIPPED")
    if not line.reservation_id:
        raise rule_violation(f"{line.sku} is not allocated yet — allocate it before packing", code="LINE_NOT_ALLOCATED")
    reservation = Reservation.query.filter_by(tenant_id=tenant_id, id=line.reservation_id).first()
    assert_warehouse_in_scope(actor, reservation.warehouse_id)

    quantity = to_decimal(body.quantity)
    if quantity <= 0:
        raise rule_violation("Quantity packed must be greater than zero", code="INVALID_QUANTITY")
    remaining = to_decimal(line.allocated_qty) - to_decimal(line.packed_qty)
    if quantity > remaining:
        raise rule_violation(f"Only {decimal_str(remaining)} of {line.sku} remains to be packed", code="PACK_QTY_EXCEEDS_REMAINING")

    line.packed_qty = to_decimal(line.packed_qty) + quantity
    order = order_repo.require_order(tenant_id, line.order_id)
    _recompute_order_packing_status(order, order_repo.lines_of(order.id))
    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="order_line.packed", entity_type="order_line", entity_id=str(line.id), meta={"quantity": decimal_str(quantity), "packedQty": decimal_str(line.packed_qty), "sku": line.sku, "orderId": str(order.id)})
    session.commit()

    return order_repo.to_order_api(order_repo.require_order(tenant_id, order.id), order_repo.lines_of(order.id))


@router.post("/orders/lines/{line_id}/ship")
def ship_order_line(line_id: uuid_mod.UUID, body: ShipLineBody, actor: Actor = Depends(require_permission("order:ship"))):
    tenant_id = actor["tenant_id"]
    line = OrderLine.query.filter_by(tenant_id=tenant_id, id=line_id).first()
    if not line:
        raise not_found("Order line")
    if line.status == "cancelled":
        raise rule_violation(f"{line.sku} is cancelled and cannot be shipped", code="LINE_CANCELLED")
    if not line.reservation_id:
        raise rule_violation(f"{line.sku} is not allocated yet — allocate it before shipping", code="LINE_NOT_ALLOCATED")
    reservation = Reservation.query.filter_by(tenant_id=tenant_id, id=line.reservation_id).first()
    assert_warehouse_in_scope(actor, reservation.warehouse_id)

    quantity = to_decimal(body.quantity)
    if quantity <= 0:
        raise rule_violation("Quantity shipped must be greater than zero", code="INVALID_QUANTITY")
    packed_not_shipped = to_decimal(line.packed_qty) - to_decimal(line.shipped_qty)
    if quantity > packed_not_shipped:
        raise rule_violation(f"Only {decimal_str(packed_not_shipped)} of {line.sku} has been packed and is ready to ship", code="SHIP_QTY_EXCEEDS_PACKED")

    order = order_repo.require_order(tenant_id, line.order_id)
    assert_shippable(order.number, order.status)
    inventory_ledger.issue_reservation_partial(tenant_id, line.reservation_id, quantity, reference=order.number, reference_type="shipment")
    line.shipped_qty = to_decimal(line.shipped_qty) + quantity
    if to_decimal(line.shipped_qty) >= to_decimal(line.allocated_qty):
        line.status = "shipped"

    lines = order_repo.lines_of(order.id)
    _recompute_order_shipping_status(order, lines)
    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="order_line.shipped", entity_type="order_line", entity_id=str(line.id), meta={"quantity": decimal_str(quantity), "shippedQty": decimal_str(line.shipped_qty), "sku": line.sku, "orderId": str(order.id), "orderStatus": order.status})
    session.commit()

    return order_repo.to_order_api(order_repo.require_order(tenant_id, order.id), order_repo.lines_of(order.id))


@router.post("/orders/{id}/pack")
def pack_order(id: uuid_mod.UUID, actor: Actor = Depends(require_permission("order:pack"))):
    tenant_id = actor["tenant_id"]
    order = order_repo.require_order(tenant_id, id)
    if order.status not in ("allocated", "partially_allocated"):
        raise rule_violation(f"{order.number} is {order.status.replace('_', ' ')} — only an allocated order can be marked packed", code="ORDER_NOT_ALLOCATED")
    order.packing_status = "packed"
    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="order.packed", entity_type="order", entity_id=str(id), meta={"status": order.status})
    session.commit()

    return order_repo.to_order_api(order_repo.require_order(tenant_id, id), order_repo.lines_of(id))


@router.post("/orders/{id}/ship")
def ship_order(id: uuid_mod.UUID, actor: Actor = Depends(require_permission("order:ship"))):
    tenant_id = actor["tenant_id"]
    order = order_repo.require_order(tenant_id, id)
    assert_shippable(order.number, order.status)
    if order.packing_status != "packed":
        raise rule_violation(f"{order.number} has not been packed yet — mark it Packed in Production > Order Shipping first", code="ORDER_NOT_PACKED")
    lines = order_repo.lines_of(id)
    non_cancelled = [l for l in lines if l.status != "cancelled"]
    shippable = [l for l in non_cancelled if l.reservation_id and l.status != "shipped"]
    if not shippable:
        if non_cancelled and all(l.status == "shipped" for l in non_cancelled):
            raise rule_violation(f"{order.number} is already fully shipped", code="ORDER_ALREADY_SHIPPED")
        raise rule_violation(f"{order.number} has no allocated stock ready to ship — allocate the remaining line(s) first", code="ORDER_NOT_ALLOCATED")

    reservation_warehouse_ids = {
        r.warehouse_id
        for r in Reservation.query.filter(Reservation.tenant_id == tenant_id, Reservation.id.in_([l.reservation_id for l in shippable])).all()
    }
    for warehouse_id in reservation_warehouse_ids:
        assert_warehouse_in_scope(actor, warehouse_id)

    for line in shippable:
        inventory_ledger.issue_reservation(tenant_id, line.reservation_id, order.number, reference_type="shipment")
        line.shipped_qty = line.quantity
        line.status = "shipped"

    order.status = "shipped" if all(l.status == "shipped" for l in non_cancelled) else "partially_shipped"
    order.shipped_at = datetime.now(timezone.utc)
    shipped_warehouse_ids = sorted({str(r.warehouse_id) for r in Reservation.query.filter(Reservation.tenant_id == tenant_id, Reservation.id.in_([l.reservation_id for l in shippable])).all()})
    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="order.shipped", entity_type="order", entity_id=str(id), meta={"warehouseIds": shipped_warehouse_ids, "status": order.status})
    session.commit()

    return order_repo.to_order_api(order_repo.require_order(tenant_id, id), order_repo.lines_of(id))


@router.post("/orders/{id}/cancel")
def cancel_order(id: uuid_mod.UUID, body: CancelBody, actor: Actor = Depends(require_permission("order:cancel"))):
    tenant_id = actor["tenant_id"]
    order = order_repo.require_order(tenant_id, id)
    assert_transition(order.number, order.status, "cancelled")

    for line in order_repo.lines_of(id):
        if line.reservation_id and line.status not in ("shipped", "cancelled"):
            inventory_ledger.release_reservation(tenant_id, line.reservation_id, f"{order.number} cancelled")
        if line.status != "shipped":
            line.status = "cancelled"

    apply_credit_usage_for_party(tenant_id, order.customer_id, delta=decimal_str(-to_decimal(order.total)), reference=order.number, allow_override=True)

    order.status = "cancelled"
    order.cancelled_reason = body.reason
    order.cancelled_at = datetime.now(timezone.utc)
    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="order.cancelled", entity_type="order", entity_id=str(id), reason=body.reason)
    session.commit()

    return order_repo.to_order_api(order_repo.require_order(tenant_id, id), order_repo.lines_of(id))


@router.get("/orders/{id}/audit")
def order_audit(id: uuid_mod.UUID, actor: Actor = Depends(require_permission("order:read"))):
    rows = read_audit_trail(tenant_id=actor["tenant_id"], entity_type="order", entity_id=str(id))
    return {"data": [{"id": str(r.id), "actor_id": str(r.actor_id) if r.actor_id else None, "actor_email": r.actor_email, "action": r.action, "reason": r.reason, "created_at": r.created_at.isoformat() if r.created_at else None} for r in rows]}



_DIGITS_RE = re.compile(r"\d+")


@router.post("/orders/{id}/invoice", status_code=201)
def invoice_order(id: uuid_mod.UUID, body: InvoiceBody, actor: Actor = Depends(require_permission("order:invoice"))):
    tenant_id = actor["tenant_id"]
    order = order_repo.require_order(tenant_id, id)
    assert_invoiceable(order.number, order.status)
    if order.invoice_id:
        raise rule_violation(f"{order.number} has already been invoiced as {order.invoice_number}", code="ORDER_ALREADY_INVOICED")
    lines = order_repo.lines_of(id)

    assert_invoice_matches_order(order.number, order.total, order.total)

    if body.businessEntityId:
        entity = BusinessEntity.query.filter_by(tenant_id=tenant_id, id=body.businessEntityId).first()
        if not entity:
            raise not_found("Business entity")
        if entity.status != "active":
            raise rule_violation(f"Business entity {entity.code} is {entity.status}", code="BUSINESS_ENTITY_INACTIVE")

    try:
        customer = party_summary.build_summary_by_id(tenant_id, order.customer_id)
    except ProblemError:
        customer = None
    # Orders carry no warehouse of their own - by invoice time the order has
    # always already been allocated (and usually shipped), so the supplying
    # warehouse is derived from the lines' actual reservations. If lines were
    # allocated from warehouses in different states, this picks the earliest
    # one; true multi-place-of-supply invoicing is out of scope.
    supplier_warehouse_id = order_repo.primary_reservation_warehouse_id(tenant_id, lines)
    warehouse = warehouse_repo.get_warehouse_summary(tenant_id, supplier_warehouse_id) if supplier_warehouse_id else None
    # Place of supply is the customer's own registered (billing/GSTIN) state,
    # not the delivery address on this particular order: the supplying
    # warehouse's state is compared to the customer's, never the destination.
    supplier_state = warehouse.get("stateCode") if warehouse else None
    customer_state = customer.get("stateCode") if customer else None
    intra_state = bool(supplier_state and customer_state and supplier_state == customer_state)
    gst = split_gst(order.tax_total, intra_state)

    if body.dueDate:
        due_date = body.dueDate
    else:
        match = _DIGITS_RE.search(order.payment_terms or "")
        payment_days = int(match.group()) if match else settings.default_payment_days
        due_date = order.order_date + timedelta(days=payment_days)

    number = next_document_number(tenant_id, settings.invoice_number_prefix, pad=4, start=9900)
    invoice = Invoice(
        tenant_id=tenant_id,
        number=number,
        order_id=order.id,
        customer_id=order.customer_id,
        customer_name=order.customer_name,
        business_entity_id=body.businessEntityId,
        invoice_date=date.today(),
        due_date=due_date,
        currency=order.currency,
        subtotal=order.subtotal,
        tax_total=order.tax_total,
        charges=order.charges,
        total=order.total,
        cgst=gst["cgst"],
        sgst=gst["sgst"],
        igst=gst["igst"],
        place_of_supply=customer_state,
        status="issued",
        email_state="not_sent",
        created_by=str(actor["user_id"]),
    )
    session.add(invoice)
    session.flush()

    for i, line in enumerate(lines):
        session.add(
            InvoiceLine(
                tenant_id=tenant_id,
                invoice_id=invoice.id,
                order_line_id=line.id,
                line_no=i + 1,
                sku=line.sku,
                description=line.description,
                quantity=line.quantity,
                uom=line.uom,
                unit_price=line.unit_price,
                tax_code=line.tax_code,
                tax_rate=line.tax_rate,
                net_amount=line.net_amount,
                tax_amount=line.tax_amount,
                gross_amount=line.gross_amount,
            )
        )

    # Order status is untouched - invoicing is decoupled from the
    # fulfillment lifecycle (see order_state.py's module docstring). Whether
    # an order has been invoiced is tracked purely via invoice_id/
    # invoice_number, shown as its own "Invoiced" tag rather than folded
    # into status.
    order.invoice_id = invoice.id
    order.invoice_number = number

    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="order.invoiced", entity_type="order", entity_id=str(id), meta={"invoiceNumber": number, "total": decimal_str(order.total)})

    # Finance's post_receivable(), un-swallowed, in the same transaction. The
    # original's real call site omits orderNumber/customerName/taxAmount
    # entirely - Finance defaults those to null/"Customer"/0, so the resulting
    # AR row's customer_name really is the literal placeholder "Customer",
    # not the order's real customer. Faithful, not a bug to fix.
    finance_repo.post_receivable(tenant_id, order_id=order.id, customer_id=order.customer_id, invoice_id=invoice.id, invoice_number=invoice.number, amount=invoice.total, currency=invoice.currency, due_date=invoice.due_date)
    finance_repo.ensure_period_open(tenant_id, invoice.invoice_date)

    products = product_repo.get_summaries(tenant_id, [l.product_id for l in lines])
    customer_tax_id = customer.get("taxId") if customer else None
    billing_address = (customer.get("billingAddress") if customer else None) or {}
    shipping_address = (customer.get("shippingAddress") if customer else None) or {}
    bill_to = {**billing_address, "name": order.customer_name, "taxId": customer_tax_id}
    ship_to = {**shipping_address, "name": order.customer_name, "taxId": customer_tax_id}

    pdf = document_repo.render_document(
        tenant_id,
        template="customer-invoice",
        data={
            "number": invoice.number,
            "seller": org_repo.resolve_seller(tenant_id, invoice.business_entity_id),
            "customer": order.customer_name,
            "invoiceDate": invoice.invoice_date.strftime("%d %b %Y"),
            "dueDate": invoice.due_date.strftime("%d %b %Y"),
            "orderNumber": order.number,
            "poNumber": order.customer_ref,
            "billTo": bill_to,
            "shipTo": ship_to,
            "intraState": intra_state,
            "lines": [
                {
                    "sku": line.sku,
                    "description": line.description,
                    "hsnCode": products.get(str(line.product_id), {}).get("hsnCode"),
                    "quantity": decimal_str(line.quantity),
                    "uom": line.uom,
                    "unitPrice": decimal_str(line.unit_price),
                    "netAmount": decimal_str(line.net_amount),
                    "taxRate": decimal_str(line.tax_rate),
                    "grossAmount": decimal_str(line.gross_amount),
                }
                for line in lines
            ],
            "subtotal": decimal_str(invoice.subtotal),
            "gst": {"cgst": decimal_str(invoice.cgst), "sgst": decimal_str(invoice.sgst), "igst": decimal_str(invoice.igst)},
            "total": decimal_str(invoice.total),
            "currency": invoice.currency,
        },
        filename=f"{invoice.number}.pdf",
        related_type="invoice",
        related_id=str(invoice.id),
        created_by=str(actor["user_id"]),
    )
    invoice.document_id = pdf["id"]

    to = body.to if body.to else ([customer["email"]] if customer and customer.get("email") else [])
    if to:
        try:
            # Faithful port of a real bug: the original's own invoice.issued
            # call omits `currency` from its data payload even though the
            # template references {{currency}} - the rendered email literally
            # shows a blank there. Do not add it.
            result = notification_repo.send_notification(
                tenant_id,
                template="invoice.issued",
                to=to,
                data={"number": invoice.number, "total": decimal_str(invoice.total), "dueDate": invoice.due_date.isoformat(), "pdfUrl": pdf["url"]},
                related_type="invoice",
                related_id=str(invoice.id),
            )
            invoice.email_state = notification_repo.delivery_state(result)
            invoice.email_error = result.get("error")
        except ProblemError as exc:
            invoice.email_state = "failed"
            invoice.email_error = exc.detail
    else:
        invoice.email_state = "failed"
        invoice.email_error = "No recipient email address on file"

    session.commit()

    return {
        "order": order_repo.to_order_api(order_repo.require_order(tenant_id, id), order_repo.lines_of(id)),
        "invoice": {"id": str(invoice.id), "number": invoice.number, "total": decimal_str(invoice.total)},
    }


#  Finance's Invoices tab downloads invoices via this route directly, and
#  is the only caller outside the Documents module itself, so it also
#  accepts finance:read.
@router.get("/orders/{id}/invoice/download")
def download_order_invoice(id: uuid_mod.UUID, actor: Actor = Depends(require_any_permission("document:read", "finance:read"))):
    """Streams the PDF generated by invoice_order() for this order - lets a
    user re-download an already-generated invoice any number of times
    without re-generating it. Falls back to looking the document up by
    related_type/related_id (rather than requiring Invoice.document_id) so
    invoices issued before that column started being populated still
    download correctly."""
    tenant_id = actor["tenant_id"]
    order = order_repo.require_order(tenant_id, id)
    if not order.invoice_id:
        raise not_found("Invoice")
    invoice = Invoice.query.filter_by(tenant_id=tenant_id, id=order.invoice_id).first()
    if not invoice:
        raise not_found("Invoice")

    document_id = invoice.document_id
    if not document_id:
        doc = Document.query.filter_by(tenant_id=tenant_id, related_type="invoice", related_id=str(invoice.id)).order_by(Document.created_at.desc()).first()
        document_id = str(doc.id) if doc else None
    if not document_id:
        raise not_found("Invoice document")

    row = document_repo.require_document(tenant_id, uuid_mod.UUID(str(document_id)))
    document_repo.ensure_rendered(row)  # ASYNC_PDF: the worker may not have got to it yet
    try:
        data = document_storage.get(row.storage_key)
    except FileNotFoundError:
        # Local dev storage lives under /tmp, which doesn't survive a machine
        # reboot - the Document row can outlive its file. A clear 409 beats a
        # raw 500 here.
        raise conflict(f"{invoice.number}'s stored PDF is no longer available", code="DOCUMENT_FILE_MISSING")
    return Response(content=data, media_type=row.content_type, headers={"Content-Disposition": f'attachment; filename="{row.filename}"'})


@router.post("/orders/{id}/fulfill")
def fulfill_order(id: uuid_mod.UUID, body: FulfillBody, actor: Actor = Depends(require_permission("order:ship"))):
    """Marks an order Fulfilled or Partially Fulfilled. Unlike every other
    status, this one is never derived - "received by the customer" isn't
    something this system observes, so it's only ever set by a human saying
    so, once the order has shipped (or, for orders invoiced under the old
    pre-decoupling flow, once invoiced - order_state.py's _TRANSITIONS keeps
    both paths)."""
    tenant_id = actor["tenant_id"]
    order = order_repo.require_order(tenant_id, id)
    target = "partially_fulfilled" if body.partial else "fulfilled"
    assert_transition(order.number, order.status, target)

    order.status = target
    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="order.fulfilled", entity_type="order", entity_id=str(id), meta={"partial": body.partial})
    session.commit()

    return order_repo.to_order_api(order_repo.require_order(tenant_id, id), order_repo.lines_of(id))


@router.post("/orders/{id}/manual-logistics")
def manual_logistics(id: uuid_mod.UUID, body: ManualLogisticsBody, actor: Actor = Depends(require_permission("logistics:write"))):
    tenant_id = actor["tenant_id"]
    order = order_repo.require_order(tenant_id, id)

    has_override_permission = permits_all(actor["permissions"], ["order:override-logistics"])
    decision = evaluate_logistics_trigger(number=order.number, settlement=settlement_position(order.total, order.paid_amount), has_override_permission=has_override_permission, override_reason=body.reason)
    assert_logistics_allowed(decision)

    request_row = logistics_repo.create_transport_request_from_order(tenant_id, order, order_repo.lines_of(id), trigger="manual-override", raised_by=str(actor["user_id"]), override_reason=decision.reason)

    order.logistics_state = "manually_raised"
    order.logistics_request_id = request_row.id
    order.logistics_override_by = str(actor["user_id"])
    order.logistics_override_reason = decision.reason
    order.logistics_raised_at = datetime.now(timezone.utc)

    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="order.logistics.manual", entity_type="order", entity_id=str(id), reason=decision.reason, meta={"transportRequestId": str(request_row.id)})
    session.commit()

    return order_repo.to_order_api(order_repo.require_order(tenant_id, id), order_repo.lines_of(id))


@router.get("/invoices")
def list_invoices(actor: Actor = Depends(require_permission("order:read")), query: ListQuery = Depends()):
    q = session.query(Invoice, Order.number).join(Order, Order.id == Invoice.order_id).filter(Invoice.tenant_id == actor["tenant_id"])
    if query.q:
        like = f"%{query.q}%"
        q = q.filter(or_(Invoice.number.ilike(like), Invoice.customer_name.ilike(like)))
    total = q.count()
    rows = q.order_by(Invoice.created_at.desc()).limit(query.limit).offset(offset_of(query)).all()

    data = [
        {
            "id": str(inv.id),
            "number": inv.number,
            "orderId": str(inv.order_id),
            "orderNumber": order_number,
            "customerId": str(inv.customer_id),
            "customerName": inv.customer_name,
            "businessEntityId": str(inv.business_entity_id) if inv.business_entity_id else None,
            "invoiceDate": inv.invoice_date.isoformat() if inv.invoice_date else None,
            "dueDate": inv.due_date.isoformat() if inv.due_date else None,
            "currency": inv.currency,
            "subtotal": decimal_str(inv.subtotal),
            "taxTotal": decimal_str(inv.tax_total),
            "total": decimal_str(inv.total),
            "cgst": decimal_str(inv.cgst),
            "sgst": decimal_str(inv.sgst),
            "igst": decimal_str(inv.igst),
            "status": inv.status,
            "emailState": inv.email_state,
            "createdAt": inv.created_at.isoformat() if inv.created_at else None,
        }
        for inv, order_number in rows
    ]
    return list_response(data, query, total)
