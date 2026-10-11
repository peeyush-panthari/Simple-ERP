"""The "control tower" dashboard - a from-scratch, monolith-appropriate
substitute for Node's analytics service.

Node's real /dashboard composes 6 panels: finance working-capital and
inventory valuation via synchronous cross-service HTTP calls, an order
funnel + cycle-time report queried from a locally-owned `order_cycle` table,
ticket stats via HTTP, and 12 recent rows from a locally-owned `event_stream`
table. Both `order_cycle` and `event_stream` are read-model projections built
by an async Kafka/Redis consumer (`analytics-projection`) that subscribes to
every domain event published through each service's own transactional
outbox - a mechanism this monolith deliberately doesn't have (direct
in-process function calls do that job instead; see the document/notification
modules' own design notes, and system_status.py's module docstring for the
same call made for the old service-map page).

Rather than build an event-sourcing/outbox layer across every already-shipped
module just to feed one page, this recomputes the same information live,
directly from the tables that already exist:
  - working capital / inventory valuation: already-built finance_repo /
    inventory_ledger functions, called in-process (no HTTP hop needed).
  - order funnel: Order.status mapped onto the same 5 buckets Node's
    order_cycle table encoded as timestamp columns - live, not projected,
    so it's never stale, at the cost of not knowing exactly when an order
    entered its current stage.
  - cycle times: computed live via joins over Order -> ArInvoice ->
    PaymentAllocation -> Payment, the same tables (and largely the same
    per-row-latest-payment pattern) finance_repo.working_capital_report's
    sibling /working-capital/cycle route already uses for DSO/DPO.
  - recent activity: substituted with the existing audit log (real actor
    actions, not domain events) - the closest analog that already exists,
    clearly relabeled rather than claimed to be the same thing.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func

from app.core.db import session
from app.models.ar_invoice import ArInvoice
from app.models.order import Order
from app.models.payment import Payment
from app.models.payment_allocation import PaymentAllocation
from app.core.audit import read_audit_trail
from app.core.money import decimal_str, to_decimal

_FUNNEL_STAGES = ["Confirmed", "Under production", "Dispatched", "Invoiced", "Fulfilled"]

_STATUS_TO_STAGE = {
    # Aligned with order_state.STATUS_LABELS, collapsed to five funnel
    # stages: no 'picked' stage anymore (there's no picked status to bucket
    # into it), and 'invoiced' now gets its own stage rather than being
    # folded into "Fulfilled" - that stage means only the (manually set)
    # fulfilled/partially_fulfilled statuses now that those actually exist.
    "confirmed": "Confirmed",
    "allocated": "Under production",
    "partially_allocated": "Under production",
    "shipped": "Dispatched",
    "partially_shipped": "Dispatched",
    "invoiced": "Invoiced",
    "fulfilled": "Fulfilled",
    "partially_fulfilled": "Fulfilled",
}


def panel(source: str, available: bool, data: dict | list | None, error: str | None = None) -> dict:
    """Same shape as Node's panel() wrapper - lets one dead/unbuilt
    dependency degrade a single card instead of failing the whole page."""
    return {"available": available, "source": source, "data": data, "error": error}


def order_funnel(tenant_id: uuid.UUID) -> list[dict]:
    """Cancelled orders are excluded entirely (their pipeline stage is moot),
    matching the same spirit as Node's own funnel omitting them from any
    meaningful stage."""
    rows = Order.query.filter(Order.tenant_id == tenant_id, Order.status != "cancelled").all()
    counts = {stage: {"count": 0, "value": to_decimal(0)} for stage in _FUNNEL_STAGES}
    for o in rows:
        stage = _STATUS_TO_STAGE.get(o.status)
        if not stage:
            continue
        counts[stage]["count"] += 1
        counts[stage]["value"] += to_decimal(o.total or 0)
    return [{"stage": stage, "count": counts[stage]["count"], "value": decimal_str(counts[stage]["value"])} for stage in _FUNNEL_STAGES]


def _latest_payment_dates(ar_invoice_ids: list[uuid.UUID]) -> dict[uuid.UUID, date]:
    """Batched replacement for a per-invoice PaymentAllocation + Payment
    lookup: one query for the latest allocation per invoice (via a window
    function), joined straight to Payment, instead of two queries per order
    in the cycle_times() loop."""
    if not ar_invoice_ids:
        return {}
    from sqlalchemy import func

    row_number = func.row_number().over(partition_by=PaymentAllocation.ar_invoice_id, order_by=PaymentAllocation.created_at.desc()).label("rn")
    ranked = (
        session.query(PaymentAllocation.ar_invoice_id, PaymentAllocation.payment_id, row_number)
        .filter(PaymentAllocation.ar_invoice_id.in_(ar_invoice_ids))
        .subquery()
    )
    rows = (
        session.query(ranked.c.ar_invoice_id, Payment.payment_date)
        .join(Payment, Payment.id == ranked.c.payment_id)
        .filter(ranked.c.rn == 1)
        .all()
    )
    return {ar_invoice_id: payment_date for ar_invoice_id, payment_date in rows}


def cycle_times(tenant_id: uuid.UUID) -> dict:
    cutoff = date.today() - timedelta(days=180)
    orders = Order.query.filter(Order.tenant_id == tenant_id, Order.order_date >= cutoff, Order.status != "cancelled").all()
    order_ids = [o.id for o in orders]
    ar_by_order = {}
    if order_ids:
        for ar in ArInvoice.query.filter(ArInvoice.tenant_id == tenant_id, ArInvoice.order_id.in_(order_ids)).all():
            ar_by_order[ar.order_id] = ar

    latest_payment_by_ar = _latest_payment_dates([ar.id for ar in ar_by_order.values()])

    order_to_ship, ship_to_invoice, invoice_to_cash, order_to_cash = [], [], [], []
    sample = 0
    for o in orders:
        if not o.shipped_at:
            continue
        sample += 1
        shipped_date = o.shipped_at.astimezone(timezone.utc).date() if isinstance(o.shipped_at, datetime) else o.shipped_at
        order_to_ship.append((shipped_date - o.order_date).days)

        ar = ar_by_order.get(o.id)
        if not ar:
            continue
        ship_to_invoice.append((ar.invoice_date - shipped_date).days)

        payment_date = latest_payment_by_ar.get(ar.id)
        if payment_date:
            invoice_to_cash.append((payment_date - ar.invoice_date).days)
            order_to_cash.append((payment_date - o.order_date).days)

    def _avg(values: list[int]) -> str | None:
        return f"{sum(values) / len(values):.2f}" if values else None

    return {
        "unit": "days",
        "sampleSize": sample,
        "orderToShip": _avg(order_to_ship),
        "shipToInvoice": _avg(ship_to_invoice),
        "invoiceToCash": _avg(invoice_to_cash),
        "orderToCash": _avg(order_to_cash),
    }


def recent_activity(tenant_id: uuid.UUID, limit: int = 12) -> list[dict]:
    rows = read_audit_trail(tenant_id=tenant_id, limit=limit)
    return [
        {
            "id": str(r.id),
            "action": r.action,
            "actorEmail": r.actor_email,
            "entityType": r.entity_type,
            "entityId": r.entity_id,
            "createdAt": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


def dashboard(tenant_id: uuid.UUID) -> dict:
    from app.services import finance_repo, inventory_ledger

    try:
        inv = inventory_ledger.compute_valuation(tenant_id)
        inv_panel = panel("inventory", True, inv)
    except Exception as exc:  # noqa: BLE001
        inv = None
        inv_panel = panel("inventory", False, None, str(exc))

    # Reuse the valuation just computed above instead of making
    # working_capital_report() redo the same full stock_ledger scan.
    wc = finance_repo.working_capital_report(tenant_id, date.today(), precomputed_valuation=inv)

    return {
        "asOf": datetime.now(timezone.utc).isoformat(),
        "workingCapital": panel("finance", True, wc),
        "inventory": inv_panel,
        "orderFunnel": order_funnel(tenant_id),
        "cycleTimes": cycle_times(tenant_id),
        "recentActivity": recent_activity(tenant_id),
    }
