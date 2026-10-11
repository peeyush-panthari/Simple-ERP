"""Order queries + API projections. Ported 1:1 from
backend_py/app/services/order_repo.py (`mark_dispatched`/`mark_delivered`/
`apply_settlement` - the logistics/finance event-consumer equivalents -
restored now that those domains are ported).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.core.errors import not_found
from app.core.db import session
from app.core.audit import audit
from app.core.money import decimal_str, to_decimal
from app.models.document import Document
from app.models.finished_good_allocation import FinishedGoodAllocation
from app.models.finished_good_item import FinishedGoodItem
from app.models.order import Order
from app.models.order_line import OrderLine
from app.models.product import Product
from app.models.reservation import Reservation
from app.services import document_storage
from app.services.order_settlement import settlement_position


def find_order(tenant_id: uuid.UUID, order_id: uuid.UUID) -> Order | None:
    return Order.query.filter_by(tenant_id=tenant_id, id=order_id).first()


def require_order(tenant_id: uuid.UUID, order_id: uuid.UUID) -> Order:
    order = find_order(tenant_id, order_id)
    if not order:
        raise not_found("Sales order")
    return order


def lock_order(tenant_id: uuid.UUID, order_id: uuid.UUID) -> Order | None:
    return session.query(Order).filter_by(tenant_id=tenant_id, id=order_id).with_for_update().first()


def lines_of(order_id: uuid.UUID) -> list[OrderLine]:
    return OrderLine.query.filter_by(order_id=order_id).order_by(OrderLine.line_no).all()


def primary_reservation_warehouse_id(tenant_id: uuid.UUID, lines: list[OrderLine]) -> uuid.UUID | None:
    """Orders no longer carry their own warehouse_id - it's only known once
    stock is actually allocated to a line, via that line's Reservation. For
    callers needing exactly one warehouse for the whole order, this picks
    the earliest-allocated line's warehouse."""
    reservation_ids = [l.reservation_id for l in lines if l.reservation_id]
    if not reservation_ids:
        return None
    reservation = Reservation.query.filter(Reservation.tenant_id == tenant_id, Reservation.id.in_(reservation_ids)).order_by(Reservation.created_at).first()
    return reservation.warehouse_id if reservation else None


# ---- API projections --------------------------------------------------------


def to_order_api(row: Order, lines: list[OrderLine] | None = None) -> dict:
    from app.services.order_state import STATUS_LABELS

    settlement = settlement_position(row.total, row.paid_amount)
    result = {
        "id": str(row.id),
        "number": row.number,
        "customerId": str(row.customer_id),
        "customerName": row.customer_name,
        "customerRef": row.customer_ref,
        "status": row.status,
        "statusLabel": STATUS_LABELS[row.status],
        "packingStatus": row.packing_status,
        "orderDate": row.order_date.isoformat() if row.order_date else None,
        "promisedDate": row.promised_date.isoformat() if row.promised_date else None,
        "warehouseId": str(row.warehouse_id) if row.warehouse_id else None,
        "warehouseCode": row.warehouse_code,
        "currency": row.currency,
        "exchangeRate": decimal_str(row.exchange_rate),
        "subtotal": decimal_str(row.subtotal),
        "taxTotal": decimal_str(row.tax_total),
        "charges": decimal_str(row.charges),
        "total": decimal_str(row.total),
        "paidAmount": decimal_str(row.paid_amount),
        "fullyPaid": row.fully_paid,
        "outstanding": settlement.outstanding,
        "paidPercent": settlement.paid_percent,
        "paymentTerms": row.payment_terms,
        "deliveryAddress": {
            "line1": row.delivery_line1,
            "line2": row.delivery_line2,
            "city": row.delivery_city,
            "stateCode": row.delivery_state_code,
            "postalCode": row.delivery_postal_code,
            "country": row.delivery_country,
        },
        "notes": row.notes,
        "inverterDetails": row.inverter_details,
        "accessoriesRequired": row.accessories_required,
        "branding": row.branding,
        "logisticsCostBorneBy": row.logistics_cost_borne_by,
        "logisticsState": row.logistics_state,
        "logisticsRequestId": str(row.logistics_request_id) if row.logistics_request_id else None,
        "logisticsOverrideBy": row.logistics_override_by,
        "logisticsOverrideReason": row.logistics_override_reason,
        "invoiceId": str(row.invoice_id) if row.invoice_id else None,
        "invoiceNumber": row.invoice_number,
        "cancelledReason": row.cancelled_reason,
        "shippedAt": row.shipped_at.isoformat() if row.shipped_at else None,
        "closedAt": row.closed_at.isoformat() if row.closed_at else None,
        "createdBy": row.created_by,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
        "settlement": {
            "total": settlement.total,
            "paidAmount": settlement.paid_amount,
            "outstanding": settlement.outstanding,
            "fullyPaid": settlement.fully_paid,
            "paidPercent": settlement.paid_percent,
        },
    }
    if lines is not None:
        allocations = _line_allocations(row.tenant_id, lines)
        names = _product_names(row.tenant_id, lines)
        result["lines"] = [{**to_line_api(l, product_name=names.get(l.product_id)), "allocation": allocations.get(str(l.id))} for l in lines]
        result["inverterAttachment"] = _order_attachment(row.tenant_id, row.id)
    return result


def _product_names(tenant_id: uuid.UUID, lines: list[OrderLine]) -> dict[uuid.UUID, str]:
    product_ids = {l.product_id for l in lines}
    if not product_ids:
        return {}
    rows = Product.query.filter(Product.tenant_id == tenant_id, Product.id.in_(product_ids)).with_entities(Product.id, Product.name).all()
    return {r[0]: r[1] for r in rows}


def _order_attachment(tenant_id: uuid.UUID, order_id: uuid.UUID) -> dict | None:
    doc = (
        Document.query.filter_by(tenant_id=tenant_id, related_type="order", related_id=str(order_id))
        .order_by(Document.created_at.desc())
        .first()
    )
    if not doc:
        return None
    return {"id": str(doc.id), "filename": doc.filename, "url": document_storage.url_for(doc.id, doc.storage_key)}


def _line_allocations(tenant_id: uuid.UUID, lines: list[OrderLine]) -> dict[str, dict]:
    """Which stock is actually behind each allocated line - keyed by order_line id."""
    ids = [l.reservation_id for l in lines if l.reservation_id]
    if not ids:
        return {}
    reservations = {r.id: r for r in Reservation.query.filter(Reservation.tenant_id == tenant_id, Reservation.id.in_(ids)).all()}
    allocation_rows = FinishedGoodAllocation.query.filter(FinishedGoodAllocation.tenant_id == tenant_id, FinishedGoodAllocation.reservation_id.in_(ids)).all()
    item_ids = {a.finished_good_item_id for a in allocation_rows if a.finished_good_item_id}
    items_by_id = {i.id: i for i in FinishedGoodItem.query.filter(FinishedGoodItem.tenant_id == tenant_id, FinishedGoodItem.id.in_(item_ids)).all()} if item_ids else {}
    inventory_ids_by_reservation: dict[uuid.UUID, list[str]] = {}
    for a in allocation_rows:
        item = items_by_id.get(a.finished_good_item_id) if a.finished_good_item_id else None
        if item:
            inventory_ids_by_reservation.setdefault(a.reservation_id, []).append(item.inventory_id)

    result = {}
    for l in lines:
        r = reservations.get(l.reservation_id) if l.reservation_id else None
        if r:
            result[str(l.id)] = {
                "reservationId": str(r.id),
                "batchNo": r.batch_no,
                "quantity": decimal_str(r.quantity),
                "status": r.status,
                "inventoryIds": sorted(inventory_ids_by_reservation.get(r.id, [])),
            }
    return result


def to_line_api(line: OrderLine, product_name: str | None = None) -> dict:
    return {
        "id": str(line.id),
        "lineNo": line.line_no,
        "productId": str(line.product_id),
        "sku": line.sku,
        "productName": product_name,
        "description": line.description,
        "quantity": decimal_str(line.quantity),
        "uom": line.uom,
        "unitPrice": decimal_str(line.unit_price),
        "discount": decimal_str(line.discount),
        "taxCode": line.tax_code,
        "taxRate": decimal_str(line.tax_rate),
        "netAmount": decimal_str(line.net_amount),
        "taxAmount": decimal_str(line.tax_amount),
        "grossAmount": decimal_str(line.gross_amount),
        "reservationId": str(line.reservation_id) if line.reservation_id else None,
        "allocatedQty": decimal_str(line.allocated_qty),
        "packedQty": decimal_str(line.packed_qty),
        "shippedQty": decimal_str(line.shipped_qty),
        "status": line.status,
    }


def get_summary(tenant_id: uuid.UUID, order_id: uuid.UUID) -> dict | None:
    order = find_order(tenant_id, order_id)
    if not order:
        return None
    return {
        "id": str(order.id),
        "number": order.number,
        "status": order.status,
        "warehouseId": str(order.warehouse_id) if order.warehouse_id else None,
    }


# ---- direct-call equivalents of order's DispatchCreated/DeliveryConfirmed consumers ----


def mark_dispatched(tenant_id: uuid.UUID, order_id: uuid.UUID) -> None:
    order = find_order(tenant_id, order_id)
    if not order:
        return
    order.logistics_state = "dispatched"


def mark_delivered(tenant_id: uuid.UUID, order_id: uuid.UUID, pod_url: str | None) -> None:
    order = find_order(tenant_id, order_id)
    if not order:
        return
    order.logistics_state = "delivered"
    # "invoiced" is a legacy status (see order_state.py's module docstring) -
    # kept here so already-existing invoiced orders still auto-close on
    # delivery; new orders reach this point via shipped/partially_shipped
    # instead, since invoicing no longer changes order status at all.
    if order.status in ("invoiced", "shipped", "partially_shipped"):
        order.status = "fulfilled"
        order.closed_at = datetime.now(timezone.utc)
    audit(tenant_id=tenant_id, actor_id=None, actor_email=None, action="order.delivered", entity_type="order", entity_id=str(order_id), meta={"podUrl": pod_url})


# ---- ports /internal/orders/:id/settlement - called by finance.py's
# payment-recording flow after a non-approval-blocked AR payment settles or
# partially settles an order-linked invoice ----


def apply_settlement(tenant_id: uuid.UUID, order_id: uuid.UUID, *, paid_to_date, invoice_total) -> dict | None:
    order = lock_order(tenant_id, order_id)
    if not order:
        return None
    fully_paid = to_decimal(paid_to_date) >= to_decimal(invoice_total)
    order.paid_amount = paid_to_date
    order.fully_paid = fully_paid
    audit(
        tenant_id=tenant_id,
        actor_id=None,
        actor_email=None,
        action="order.payment.mirrored",
        entity_type="order",
        entity_id=str(order_id),
        meta={"paidAmount": decimal_str(paid_to_date), "fullyPaid": fully_paid},
    )

    # Full settlement automatically raises the logistics requirement - the
    # order-to-cash loop closing without a human, matching Node's real
    # /internal/orders/:id/settlement. Guarded on logistics_request_id being
    # unset so a second/partial-then-full settlement call stays idempotent.
    if fully_paid and order.logistics_request_id is None:
        from app.services import logistics_repo
        from app.services.order_settlement import evaluate_logistics_trigger

        decision = evaluate_logistics_trigger(number=order.number, settlement=settlement_position(order.total, order.paid_amount), has_override_permission=True, override_reason=None)
        if decision.automatic:
            request_row = logistics_repo.create_transport_request_from_order(tenant_id, order, lines_of(order_id), trigger="full-payment", raised_by=None)
            order.logistics_state = "auto_raised"
            order.logistics_request_id = request_row.id
            order.logistics_raised_at = datetime.now(timezone.utc)

    return {"orderId": str(order_id), "paidAmount": decimal_str(order.paid_amount), "fullyPaid": fully_paid}
