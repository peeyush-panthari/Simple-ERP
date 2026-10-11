"""The one place a ledger row is written. Ported from
backend_py/app/services/inventory_ledger.py - only import paths changed
(`db.session` -> the plain `session` this stack uses everywhere, `app.errors`/
`app.services.audit` -> `app.core.*`); every posting rule, the idempotency
index, the advisory-lock serialisation and the reservation/issue/release
state machine are unchanged.

Everything that changes stock goes through post(): receipts, issues,
adjustments, both legs of a transfer, production consumption and output.
Centralising it is what guarantees the balance projection can never drift
from the ledger - they are updated in the same statement pair, in the same
transaction, or not at all.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import settings
from app.core.db import session
from app.models.inventory_item import InventoryItem  # noqa: F401  (re-exported for callers' type context)
from app.models.reservation import Reservation
from app.models.stock_balance import StockBalance
from app.models.stock_ledger import IDEMPOTENCY_COALESCED_BATCH_NO, IDEMPOTENCY_COALESCED_LOCATION_ID, StockLedger
from app.core import audit as audit_service
from app.core.money import decimal_str, is_positive, round_dp, to_decimal

BUCKETS = ("available", "quarantine", "damaged", "in_transit", "expired", "reserved")


@dataclass
class LedgerPosting:
    tenant_id: uuid.UUID
    product_id: uuid.UUID
    sku: str
    warehouse_id: uuid.UUID
    quantity: str
    uom: str
    bucket: str
    movement_type: str
    reference_type: str
    reference_id: str
    location_id: uuid.UUID | None = None
    batch_no: str | None = None
    expiry_date: str | None = None
    reference_no: str | None = None
    unit_cost: str | None = None
    currency: str | None = None
    reason: str | None = None
    reverses_id: uuid.UUID | None = None
    actor_id: str | None = None
    correlation_id: str | None = None


def _idempotency_elements():
    return [
        StockLedger.tenant_id,
        StockLedger.reference_type,
        StockLedger.reference_id,
        StockLedger.movement_type,
        StockLedger.product_id,
        IDEMPOTENCY_COALESCED_BATCH_NO,
        IDEMPOTENCY_COALESCED_LOCATION_ID,
    ]


def post(entry: LedgerPosting) -> dict | None:
    """Appends one ledger row and folds it into the balance projection. The
    unique index on (reference, movement, product, batch, location) makes
    this idempotent: a redelivered/retried posting inserts nothing and
    returns None, so the caller can safely retry."""
    stmt = (
        pg_insert(StockLedger)
        .values(
            tenant_id=entry.tenant_id,
            product_id=entry.product_id,
            sku=entry.sku,
            warehouse_id=entry.warehouse_id,
            location_id=entry.location_id,
            batch_no=entry.batch_no,
            expiry_date=entry.expiry_date,
            quantity=entry.quantity,
            uom=entry.uom,
            bucket=entry.bucket,
            movement_type=entry.movement_type,
            reference_type=entry.reference_type,
            reference_id=entry.reference_id,
            reference_no=entry.reference_no,
            unit_cost=entry.unit_cost,
            currency=entry.currency,
            reason=entry.reason,
            reverses_id=entry.reverses_id,
            actor_id=entry.actor_id,
            correlation_id=entry.correlation_id,
        )
        .on_conflict_do_nothing(index_elements=_idempotency_elements())
        .returning(StockLedger.id, StockLedger.seq)
    )
    row = session.execute(stmt).first()
    if row is None:
        return None

    _apply_to_balance(entry)
    return {"id": row.id, "seq": row.seq}


def _apply_to_balance(entry: LedgerPosting) -> None:
    location_key = str(entry.location_id) if entry.location_id else ""
    stmt = (
        pg_insert(StockBalance)
        .values(
            tenant_id=entry.tenant_id,
            product_id=entry.product_id,
            sku=entry.sku,
            warehouse_id=entry.warehouse_id,
            location_key=location_key,
            location_id=entry.location_id,
            batch_no=entry.batch_no or "",
            expiry_date=entry.expiry_date,
            bucket=entry.bucket,
            uom=entry.uom,
            quantity=entry.quantity,
        )
        .on_conflict_do_update(
            index_elements=["tenant_id", "product_id", "warehouse_id", "location_key", "batch_no", "bucket"],
            set_={"quantity": StockBalance.quantity + to_decimal(entry.quantity), "updated_at": func.now()},
        )
    )
    session.execute(stmt)


def reverse(original: LedgerPosting, *, original_id: uuid.UUID, reason: str, actor_id: str | None) -> dict | None:
    """Posts a pair of rows that cancel an earlier entry. Never `delete`."""
    return post(
        LedgerPosting(
            tenant_id=original.tenant_id,
            product_id=original.product_id,
            sku=original.sku,
            warehouse_id=original.warehouse_id,
            location_id=original.location_id,
            batch_no=original.batch_no,
            expiry_date=original.expiry_date,
            quantity=decimal_str(-to_decimal(original.quantity)),
            uom=original.uom,
            bucket=original.bucket,
            movement_type="reversal",
            reference_type=original.reference_type,
            reference_id=original.reference_id,
            reference_no=original.reference_no,
            reverses_id=original_id,
            reason=reason,
            actor_id=actor_id,
        )
    )


def bucket_totals(tenant_id: uuid.UUID, product_id: uuid.UUID, warehouse_id: uuid.UUID | None = None) -> dict:
    q = session.query(StockBalance.bucket, func.sum(StockBalance.quantity)).filter(StockBalance.tenant_id == tenant_id, StockBalance.product_id == product_id)
    if warehouse_id is not None:
        q = q.filter(StockBalance.warehouse_id == warehouse_id)
    rows = q.group_by(StockBalance.bucket).all()
    totals = {b: "0" for b in BUCKETS}
    for bucket, quantity in rows:
        totals[bucket] = decimal_str(quantity)
    return totals


@dataclass
class SourceBalance:
    location_id: uuid.UUID | None
    batch_no: str | None
    expiry_date: str | None
    quantity: str
    uom: str


def available_by_location(tenant_id: uuid.UUID, product_id: uuid.UUID, warehouse_id: uuid.UUID) -> list[SourceBalance]:
    """Where a product's `available` stock physically sits, soonest-expiry first."""
    rows = (
        session.query(StockBalance)
        .filter(StockBalance.tenant_id == tenant_id, StockBalance.product_id == product_id, StockBalance.warehouse_id == warehouse_id, StockBalance.bucket == "available", StockBalance.quantity > 0)
        .order_by(StockBalance.expiry_date.asc().nulls_last(), StockBalance.location_id.asc().nulls_last(), StockBalance.batch_no.asc())
        .all()
    )
    return [
        SourceBalance(
            location_id=r.location_id,
            batch_no=r.batch_no or None,
            expiry_date=r.expiry_date.isoformat() if r.expiry_date else None,
            quantity=decimal_str(r.quantity),
            uom=r.uom,
        )
        for r in rows
    ]


@dataclass
class Draw:
    source: SourceBalance | None
    quantity: str


def draw_from(sources: list[SourceBalance], quantity) -> list[Draw]:
    """Splits `quantity` across the given balances in order, returning one
    draw per source. Never raises."""
    remaining = to_decimal(quantity)
    draws: list[Draw] = []

    for source in sources:
        if remaining <= 0:
            break
        free = to_decimal(source.quantity)
        if free <= 0:
            continue
        take = remaining if free >= remaining else free
        draws.append(Draw(source=source, quantity=decimal_str(take)))
        remaining -= take

    if remaining > 0:
        draws.append(Draw(source=None, quantity=decimal_str(remaining)))
    return draws


# ---- direct-call equivalents of the GRN posting/putaway consumers ---------


def post_grn_receipt(tenant_id: uuid.UUID, payload: dict) -> None:
    """Accepted quantity lands in `available`, QC-failed quantity lands in
    `quarantine` at the quarantine bin - visible and valued but not
    reservable or shippable. Idempotent via post()'s unique index."""
    for line in payload["lines"]:
        accepted = to_decimal(line["acceptedQty"])
        rejected = to_decimal(line["rejectedQty"])

        if is_positive(accepted):
            post(
                LedgerPosting(
                    tenant_id=tenant_id,
                    product_id=line["productId"],
                    sku=line["sku"],
                    warehouse_id=payload["warehouseId"],
                    location_id=line.get("locationId"),
                    batch_no=line.get("batchNo"),
                    expiry_date=line.get("expiryDate"),
                    quantity=decimal_str(accepted),
                    uom=line["uom"],
                    bucket="available",
                    movement_type="receipt",
                    reference_type="grn",
                    reference_id=f"{payload['grnId']}:{line['grnLineId']}",
                    reference_no=payload["grnNumber"],
                    unit_cost=line.get("unitPrice"),
                    currency=settings.base_currency,
                    reason=f"Received against {'PO' if payload.get('poId') else 'receipt'} on {payload['grnNumber']}",
                    correlation_id=None,
                )
            )

        if is_positive(rejected):
            post(
                LedgerPosting(
                    tenant_id=tenant_id,
                    product_id=line["productId"],
                    sku=line["sku"],
                    warehouse_id=payload["warehouseId"],
                    location_id=line.get("quarantineLocationId"),
                    batch_no=line.get("batchNo"),
                    expiry_date=line.get("expiryDate"),
                    quantity=decimal_str(rejected),
                    uom=line["uom"],
                    bucket="quarantine",
                    movement_type="receipt",
                    reference_type="grn-rejected",
                    reference_id=f"{payload['grnId']}:{line['grnLineId']}",
                    reference_no=payload["grnNumber"],
                    unit_cost=line.get("unitPrice"),
                    currency=settings.base_currency,
                    reason=f"QC-failed quantity quarantined from {payload['grnNumber']}",
                )
            )

    audit_service.audit(
        tenant_id=tenant_id,
        actor_id=None,
        actor_email=None,
        action="inventory.receipt.posted",
        entity_type="grn",
        entity_id=str(payload["grnId"]),
        meta={"grn": payload["grnNumber"], "lines": len(payload["lines"])},
    )


def post_putaway_transfer(tenant_id: uuid.UUID, payload: dict) -> None:
    """Stock physically moves from the receiving bay to its storage bin - two
    signed ledger rows per move rather than an update, so the balance
    projection folds them and the history keeps showing the material was in
    the bay first."""
    for line in payload["lines"]:
        quantity = to_decimal(line["quantity"])
        if not is_positive(quantity):
            continue

        if line.get("fromLocationId") and line["fromLocationId"] != line["toLocationId"]:
            post(
                LedgerPosting(
                    tenant_id=tenant_id,
                    product_id=line["productId"],
                    sku=line["sku"],
                    warehouse_id=payload["warehouseId"],
                    location_id=line["fromLocationId"],
                    batch_no=line.get("batchNo"),
                    expiry_date=line.get("expiryDate"),
                    quantity=decimal_str(-quantity),
                    uom=line["uom"],
                    bucket="available",
                    movement_type="transfer_out",
                    reference_type="putaway",
                    reference_id=f"{line['putawayId']}:out",
                    reference_no=payload["grnNumber"],
                    reason=f"Putaway from {line.get('fromLocationCode') or 'receiving'} to {line['toLocationCode']}",
                )
            )

        post(
            LedgerPosting(
                tenant_id=tenant_id,
                product_id=line["productId"],
                sku=line["sku"],
                warehouse_id=payload["warehouseId"],
                location_id=line["toLocationId"],
                batch_no=line.get("batchNo"),
                expiry_date=line.get("expiryDate"),
                quantity=decimal_str(quantity),
                uom=line["uom"],
                bucket="available",
                movement_type="transfer_in",
                reference_type="putaway",
                reference_id=f"{line['putawayId']}:in",
                reference_no=payload["grnNumber"],
                reason=f"Putaway from {line.get('fromLocationCode') or 'receiving'} to {line['toLocationCode']}",
            )
        )

    audit_service.audit(
        tenant_id=tenant_id,
        actor_id=None,
        actor_email=None,
        action="inventory.putaway.posted",
        entity_type="grn",
        entity_id=str(payload["grnId"]),
        meta={"grn": payload["grnNumber"], "moves": len(payload["lines"])},
    )


def move_bucket(
    tenant_id: uuid.UUID,
    *,
    product_id: uuid.UUID,
    sku: str,
    warehouse_id: uuid.UUID,
    location_id: uuid.UUID | None,
    batch_no: str | None,
    uom: str,
    quantity,
    from_bucket: str,
    to_bucket: str,
    reference_type: str,
    reference_id: str,
    reference_no: str | None,
    reason: str | None,
    actor_id: str | None = None,
) -> None:
    """Moves `quantity` from one bucket to another at the same (product,
    warehouse, batch, location) - two ledger legs. The idempotency index
    doesn't include `bucket`, so the legs go on a suffixed `reference_type`
    (not `reference_id`) so a referenceId-filtered movement-history query
    still finds both legs under the caller's own id."""
    common = dict(
        tenant_id=tenant_id,
        product_id=product_id,
        sku=sku,
        warehouse_id=warehouse_id,
        location_id=location_id,
        batch_no=batch_no,
        uom=uom,
        movement_type="status_change",
        reference_id=reference_id,
        reference_no=reference_no,
        reason=reason,
        actor_id=actor_id,
    )
    post(LedgerPosting(reference_type=f"{reference_type}:out", quantity=decimal_str(-to_decimal(quantity)), bucket=from_bucket, **common))
    post(LedgerPosting(reference_type=f"{reference_type}:in", quantity=decimal_str(quantity), bucket=to_bucket, **common))


def lock_stock(tenant_id: uuid.UUID, product_id: uuid.UUID, warehouse_id: uuid.UUID) -> None:
    """Serialises every write that touches one product in one warehouse via a
    transaction-scoped Postgres advisory lock keyed on (product, warehouse)."""
    key = f"{tenant_id}:{product_id}:{warehouse_id}"
    session.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(key, 0))))


# ---- reservations -----------------------------------------------------------


def _batch_candidates(tenant_id: uuid.UUID, product_id: uuid.UUID, warehouse_id: uuid.UUID, batch_no: str | None):
    from app.services.allocation import BatchCandidate

    q = session.query(StockBalance).filter(StockBalance.tenant_id == tenant_id, StockBalance.product_id == product_id, StockBalance.warehouse_id == warehouse_id, StockBalance.bucket == "available", StockBalance.quantity > 0)
    if batch_no:
        q = q.filter(StockBalance.batch_no == batch_no)
    rows = q.all()

    received_by_batch = dict(
        session.query(func.coalesce(StockLedger.batch_no, ""), func.min(StockLedger.created_at))
        .filter(StockLedger.tenant_id == tenant_id, StockLedger.product_id == product_id, StockLedger.warehouse_id == warehouse_id)
        .group_by(StockLedger.batch_no)
        .all()
    )

    candidates = []
    for b in rows:
        batch_key = b.batch_no or ""
        received_at = received_by_batch.get(batch_key)
        candidates.append(
            BatchCandidate(
                batch_no=b.batch_no,
                location_id=str(b.location_id) if b.location_id else None,
                expiry_date=b.expiry_date.isoformat() if b.expiry_date else None,
                on_hand=decimal_str(b.quantity),
                reserved="0",
                received_at=received_at or datetime.now(timezone.utc),
            )
        )
    return candidates


def _allocation_api(a) -> dict:
    return {"batchNo": a.batch_no, "locationId": a.location_id, "expiryDate": a.expiry_date, "quantity": a.quantity}


def _reservation_legs(reservation: Reservation) -> list[dict]:
    if reservation.allocation_legs:
        return reservation.allocation_legs
    return [{"batchNo": reservation.batch_no, "locationId": str(reservation.location_id) if reservation.location_id else None, "quantity": decimal_str(reservation.quantity)}]


def _batch_finished_good_items(tenant_id: uuid.UUID, allocations) -> dict:
    from app.models.finished_good_item import FinishedGoodItem

    item_ids = {a.finished_good_item_id for a in allocations if a.finished_good_item_id}
    if not item_ids:
        return {}
    items = FinishedGoodItem.query.filter(FinishedGoodItem.tenant_id == tenant_id, FinishedGoodItem.id.in_(item_ids)).all()
    return {item.id: item for item in items}


def _reverse_reservation_hold(tenant_id: uuid.UUID, reservation: Reservation, *, reference_type: str, reference_id: str, reason: str | None) -> None:
    """Moves a reservation's held quantity back out of `reserved`, into
    `available` - shared by release_reservation and create_reservation's
    replace-an-existing-hold path."""
    from app.models.finished_good_allocation import FinishedGoodAllocation
    from app.services.finished_good_status import recompute_status

    lock_stock(tenant_id, reservation.product_id, reservation.warehouse_id)

    allocations = FinishedGoodAllocation.query.filter_by(tenant_id=tenant_id, reservation_id=reservation.id).all()
    if allocations:
        items_by_id = _batch_finished_good_items(tenant_id, allocations)
        for alloc in allocations:
            item = items_by_id.get(alloc.finished_good_item_id)
            if not item:
                continue
            move_bucket(
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
                reference_type=reference_type,
                reference_id=str(alloc.id),
                reference_no=reservation.reference_no,
                reason=reason,
            )
            item.allocated_qty = to_decimal(item.allocated_qty) - to_decimal(alloc.quantity)
            if item.allocated_order_id == reservation.order_id or to_decimal(item.allocated_qty) <= 0:
                item.allocated_order_id = None
                item.allocated_order_number = None
            recompute_status(item)
        return

    for leg in _reservation_legs(reservation):
        leg_location_id = uuid.UUID(leg["locationId"]) if leg.get("locationId") else None
        move_bucket(
            tenant_id,
            product_id=reservation.product_id,
            sku=reservation.sku,
            warehouse_id=reservation.warehouse_id,
            location_id=leg_location_id,
            batch_no=leg.get("batchNo"),
            uom=reservation.uom,
            quantity=leg["quantity"],
            from_bucket="reserved",
            to_bucket="available",
            reference_type=reference_type,
            reference_id=reference_id,
            reference_no=reservation.reference_no,
            reason=reason,
        )


def create_reservation(
    tenant_id: uuid.UUID,
    *,
    product_id: uuid.UUID,
    warehouse_id: uuid.UUID,
    quantity,
    uom: str,
    batch_no: str | None = None,
    order_id: uuid.UUID | None = None,
    order_line_id: uuid.UUID | None = None,
    reference_type: str = "order",
    reference_no: str | None = None,
    expires_at=None,
    created_by: str | None = None,
) -> dict:
    """A hold on available stock - allocating moves the requested quantity
    from the `available` bucket into `reserved`. Serialised per (product,
    warehouse) so two callers cannot both reserve the last pallet."""
    from app.core.errors import not_found, rule_violation
    from app.core.audit import audit
    from app.services import product_repo
    from app.services.allocation import allocate
    from app.services.availability import assert_sufficient, compute_availability

    product = product_repo.get_summary(tenant_id, product_id)
    if not product:
        raise not_found("Product")
    if product["uom"] != uom:
        raise rule_violation(f"{product['sku']} is stocked in {product['uom']} — a reservation in {uom} would not match the ledger", code="UOM_MISMATCH")

    lock_stock(tenant_id, product_id, warehouse_id)

    if order_line_id:
        existing = Reservation.query.filter_by(tenant_id=tenant_id, order_line_id=order_line_id, status="open").first()
        if existing:
            _reverse_reservation_hold(tenant_id, existing, reference_type="reservation-replaced", reference_id=str(existing.id), reason="Replaced by a new reservation")
            existing.status = "released"
            existing.released_reason = "Replaced by a new reservation"
            existing.released_at = datetime.now(timezone.utc)

    buckets = bucket_totals(tenant_id, product_id, warehouse_id)
    view = compute_availability(buckets)
    assert_sufficient(sku=product["sku"], requested=quantity, available_to_promise=view["availableToPromise"], uom=uom, batch_no=batch_no)

    candidates = _batch_candidates(tenant_id, product_id, warehouse_id, batch_no)
    allocations = allocate(sku=product["sku"], requested=quantity, uom=uom, candidates=candidates, strategy=settings.allocation_strategy)

    single = allocations[0] if len(allocations) == 1 else None
    reservation = Reservation(
        tenant_id=tenant_id,
        product_id=product_id,
        sku=product["sku"],
        warehouse_id=warehouse_id,
        batch_no=(single.batch_no or None) if single else batch_no,
        location_id=single.location_id if single else None,
        quantity=quantity,
        uom=uom,
        allocation_legs=[_allocation_api(a) for a in allocations],
        order_id=order_id,
        order_line_id=order_line_id,
        reference_type=reference_type,
        reference_no=reference_no,
        expires_at=expires_at,
        created_by=created_by,
    )
    session.add(reservation)
    session.flush()

    for a in allocations:
        move_bucket(
            tenant_id,
            product_id=product_id,
            sku=product["sku"],
            warehouse_id=warehouse_id,
            location_id=uuid.UUID(a.location_id) if a.location_id else None,
            batch_no=a.batch_no,
            uom=uom,
            quantity=a.quantity,
            from_bucket="available",
            to_bucket="reserved",
            reference_type="reservation-hold",
            reference_id=str(reservation.id),
            reference_no=reference_no,
            reason=f"Reserved for {reference_no or reference_type}",
        )

    audit(
        tenant_id=tenant_id,
        actor_id=None,
        actor_email=None,
        action="inventory.reserved",
        entity_type="reservation",
        entity_id=str(reservation.id),
        meta={"sku": product["sku"], "quantity": decimal_str(quantity), "allocations": [_allocation_api(a) for a in allocations]},
    )
    return {"id": str(reservation.id), "status": "open", "reservationId": str(reservation.id), "allocations": [_allocation_api(a) for a in allocations]}


def release_reservation(tenant_id: uuid.UUID, reservation_id: uuid.UUID, reason: str) -> None:
    """Releasing an already-released (or never-existent-as-open) reservation
    is a no-op, not an error - a redelivered/retried cancellation must be
    harmless."""
    from app.core.errors import not_found
    from app.core.audit import audit

    reservation = session.query(Reservation).filter_by(tenant_id=tenant_id, id=reservation_id).with_for_update().first()
    if not reservation:
        raise not_found("Reservation")
    if reservation.status != "open":
        return

    _reverse_reservation_hold(tenant_id, reservation, reference_type="reservation-release", reference_id=str(reservation_id), reason=reason)

    reservation.status = "released"
    reservation.released_at = datetime.now(timezone.utc)
    reservation.released_reason = reason

    audit(tenant_id=tenant_id, actor_id=None, actor_email=None, action="inventory.reservation.released", entity_type="reservation", entity_id=str(reservation_id), meta={"sku": reservation.sku, "quantity": decimal_str(reservation.quantity)}, reason=reason)


def issue_reservation(tenant_id: uuid.UUID, reservation_id: uuid.UUID, reference: str, reference_type: str = "shipment") -> dict:
    """Issue: the goods physically leave - debited out of `reserved` entirely.
    Idempotent - issuing an already-issued reservation returns
    `alreadyIssued: true` rather than double-issuing."""
    from app.core.errors import conflict, not_found
    from app.models.finished_good_allocation import FinishedGoodAllocation
    from app.core.audit import audit
    from app.services.finished_good_status import recompute_status

    reservation = session.query(Reservation).filter_by(tenant_id=tenant_id, id=reservation_id).with_for_update().first()
    if not reservation:
        raise not_found(f"Reservation {reservation_id}")
    if reservation.status == "issued":
        return {"reservationId": str(reservation_id), "status": "issued", "alreadyIssued": True}
    if reservation.status != "open":
        raise conflict(f"Reservation is {reservation.status} and cannot be issued", code="RESERVATION_NOT_OPEN")

    lock_stock(tenant_id, reservation.product_id, reservation.warehouse_id)

    entry = None
    for leg in _reservation_legs(reservation):
        leg_location_id = uuid.UUID(leg["locationId"]) if leg.get("locationId") else None
        posted = post(
            LedgerPosting(
                tenant_id=tenant_id,
                product_id=reservation.product_id,
                sku=reservation.sku,
                warehouse_id=reservation.warehouse_id,
                location_id=leg_location_id,
                batch_no=leg.get("batchNo"),
                quantity=decimal_str(-to_decimal(leg["quantity"])),
                uom=reservation.uom,
                bucket="reserved",
                movement_type="issue",
                reference_type=reference_type,
                reference_id=reference,
                reference_no=reference,
                reason=f"Issued against reservation {reservation.id}",
            )
        )
        entry = entry or posted

    allocations = FinishedGoodAllocation.query.filter_by(tenant_id=tenant_id, reservation_id=reservation.id).all()
    items_by_id = _batch_finished_good_items(tenant_id, allocations)
    for alloc in allocations:
        item = items_by_id.get(alloc.finished_good_item_id)
        if not item:
            continue
        item.shipped_qty = to_decimal(item.shipped_qty) + to_decimal(alloc.quantity)
        item.allocated_qty = to_decimal(item.allocated_qty) - to_decimal(alloc.quantity)
        recompute_status(item)

    reservation.status = "issued"
    reservation.issued_qty = reservation.quantity
    reservation.issued_at = datetime.now(timezone.utc)

    audit(tenant_id=tenant_id, actor_id=None, actor_email=None, action="inventory.issued", entity_type="reservation", entity_id=str(reservation_id), meta={"sku": reservation.sku, "quantity": decimal_str(reservation.quantity), "reference": reference})
    return {"reservationId": str(reservation_id), "status": "issued", "ledgerEntryId": str(entry["id"]) if entry else None}


def issue_reservation_partial(tenant_id: uuid.UUID, reservation_id: uuid.UUID, quantity, reference: str, reference_type: str = "shipment") -> dict:
    """Issue exactly `quantity` out of a reservation's still-open remainder -
    the per-line-shipment counterpart of issue_reservation."""
    from app.core.errors import conflict, not_found, rule_violation
    from app.models.finished_good_allocation import FinishedGoodAllocation
    from app.core.audit import audit
    from app.services.finished_good_status import recompute_status

    quantity = to_decimal(quantity)
    if not is_positive(quantity):
        raise rule_violation("Quantity to issue must be greater than zero", code="INVALID_QUANTITY")

    reservation = session.query(Reservation).filter_by(tenant_id=tenant_id, id=reservation_id).with_for_update().first()
    if not reservation:
        raise not_found(f"Reservation {reservation_id}")
    if reservation.status != "open":
        raise conflict(f"Reservation is {reservation.status} and cannot be issued", code="RESERVATION_NOT_OPEN")

    remaining = to_decimal(reservation.quantity) - to_decimal(reservation.issued_qty)
    if quantity > remaining:
        raise rule_violation(f"Only {decimal_str(remaining)} of this reservation remains open - cannot issue {decimal_str(quantity)}", code="ISSUE_QTY_EXCEEDS_REMAINING")

    lock_stock(tenant_id, reservation.product_id, reservation.warehouse_id)

    # post()'s idempotency key is (tenant, reference_type, reference_id,
    # movement_type, product, batch, location) - reusing `reference` (the
    # order number) here the way issue_reservation does would collide with
    # the *previous* partial ship on the same line. A fresh id per call
    # sidesteps that; `reference_no` below still carries the order number.
    call_reference_id = str(uuid.uuid4())

    entry = None
    qty_left = quantity
    remaining_legs: list[dict] = []
    for leg in _reservation_legs(reservation):
        leg_qty = to_decimal(leg["quantity"])
        if qty_left <= 0 or leg_qty <= 0:
            remaining_legs.append(leg)
            continue
        take = min(leg_qty, qty_left)
        leg_location_id = uuid.UUID(leg["locationId"]) if leg.get("locationId") else None
        posted = post(
            LedgerPosting(
                tenant_id=tenant_id,
                product_id=reservation.product_id,
                sku=reservation.sku,
                warehouse_id=reservation.warehouse_id,
                location_id=leg_location_id,
                batch_no=leg.get("batchNo"),
                quantity=decimal_str(-take),
                uom=reservation.uom,
                bucket="reserved",
                movement_type="issue",
                reference_type=reference_type,
                reference_id=call_reference_id,
                reference_no=reference,
                reason=f"Partially issued against reservation {reservation.id}",
            )
        )
        entry = entry or posted
        qty_left -= take
        leftover = leg_qty - take
        if leftover > 0:
            remaining_legs.append({**leg, "quantity": decimal_str(leftover)})
    reservation.allocation_legs = remaining_legs

    allocations = FinishedGoodAllocation.query.filter_by(tenant_id=tenant_id, reservation_id=reservation.id).order_by(FinishedGoodAllocation.created_at).all()
    items_by_id = _batch_finished_good_items(tenant_id, allocations)
    qty_left = quantity
    for alloc in allocations:
        if qty_left <= 0:
            break
        alloc_qty = to_decimal(alloc.quantity)
        take = min(alloc_qty, qty_left)
        item = items_by_id.get(alloc.finished_good_item_id)
        if item:
            item.shipped_qty = to_decimal(item.shipped_qty) + take
            item.allocated_qty = to_decimal(item.allocated_qty) - take
            recompute_status(item)
        qty_left -= take
        leftover = alloc_qty - take
        if leftover > 0:
            alloc.quantity = leftover
        else:
            session.delete(alloc)

    reservation.issued_qty = to_decimal(reservation.issued_qty) + quantity
    if reservation.issued_qty >= reservation.quantity:
        reservation.status = "issued"
        reservation.issued_at = datetime.now(timezone.utc)

    audit(tenant_id=tenant_id, actor_id=None, actor_email=None, action="inventory.issued.partial", entity_type="reservation", entity_id=str(reservation_id), meta={"sku": reservation.sku, "quantity": decimal_str(quantity), "issuedQty": decimal_str(reservation.issued_qty), "reference": reference})
    return {"reservationId": str(reservation_id), "status": reservation.status, "issuedQuantity": decimal_str(quantity), "ledgerEntryId": str(entry["id"]) if entry else None}


# ---- valuation --------------------------------------------------------------


def average_costs(tenant_id: uuid.UUID, product_ids=None) -> dict:
    """Weighted-average cost per product from its own receipt/
    production_output ledger history."""
    q = session.query(
        StockLedger.product_id,
        func.sum(StockLedger.quantity * StockLedger.unit_cost).label("value"),
        func.sum(StockLedger.quantity).label("qty"),
    ).filter(StockLedger.tenant_id == tenant_id, StockLedger.unit_cost.isnot(None), StockLedger.movement_type.in_(("receipt", "production_output")))
    if product_ids is not None:
        q = q.filter(StockLedger.product_id.in_(product_ids))
    rows = q.group_by(StockLedger.product_id).all()
    return {str(r.product_id): (to_decimal(r.value) / to_decimal(r.qty) if to_decimal(r.qty) > 0 else to_decimal(0)) for r in rows}


def compute_valuation(tenant_id: uuid.UUID, warehouse_id=None, bucket: str | None = None) -> dict:
    """Weighted-average cost x on-hand StockBalance quantities."""
    avg_costs = average_costs(tenant_id)

    q = session.query(StockBalance.product_id, func.max(StockBalance.sku).label("sku"), func.sum(StockBalance.quantity).label("quantity")).filter(
        StockBalance.tenant_id == tenant_id,
        StockBalance.bucket == bucket if bucket else StockBalance.bucket.in_(("available", "quarantine", "in_transit", "reserved")),
    )
    if warehouse_id is not None:
        ids = warehouse_id if isinstance(warehouse_id, (list, set, tuple)) else [warehouse_id]
        q = q.filter(StockBalance.warehouse_id.in_(ids))
    q = q.group_by(StockBalance.product_id).having(func.sum(StockBalance.quantity) != 0)

    rows = q.all()
    lines = []
    total = to_decimal(0)
    for r in rows:
        avg_cost = avg_costs.get(str(r.product_id), to_decimal(0))
        value = to_decimal(r.quantity) * avg_cost
        total += value
        lines.append({"productId": str(r.product_id), "sku": r.sku, "quantity": decimal_str(r.quantity), "averageCost": decimal_str(round_dp(avg_cost, 4)), "value": decimal_str(round_dp(value, 2))})
    lines.sort(key=lambda l: to_decimal(l["value"]), reverse=True)

    return {"asOf": date.today().isoformat(), "totalValue": decimal_str(round_dp(total, 2)), "lines": lines}
