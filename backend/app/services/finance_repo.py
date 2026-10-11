"""AP/AR/payment queries, API projections, and the direct-call equivalents
of Node's unauthenticated internal finance endpoints - ported 1:1 (behavior)
from backend/services/finance/src/routes/{ap,ar,payments}.ts.

post_receivable()/post_payable()/get_invoiced_qty_by_line() are the direct-
call equivalents of POST /internal/ar/invoices, POST /internal/ap/invoices,
and GET /internal/ap/invoiced - none of which have any permission guard at
all in Node, so (matching procurement_repo.get_receivable_po and
order_repo.get_summary's precedent) they're plain functions here, never
routes.

ensure_period_open() is the direct-call collapse of Node's GRNPosted/
InvoiceGenerated event handlers, which in Node do nothing of consequence
beyond lazily creating today's accounting period.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import settings
from app.core.errors import not_found
from sqlalchemy import func

from app.core.db import session
from app.models.accounting_period import AccountingPeriod
from app.models.ap_invoice import ApInvoice
from app.models.ap_invoice_line import ApInvoiceLine
from app.models.ar_invoice import ArInvoice
from app.models.order import Order
from app.models.order_line import OrderLine
from app.models.payment import Payment
from app.models.po_line import PoLine
from app.models.purchase_order import PurchaseOrder
from app.services.finance_periods import assert_period_open, period_of
from app.services.finance_settlement import position
from app.core.money import decimal_str, to_decimal
from app.services.sequences import next_document_number

# ---- periods ----------------------------------------------------------------


def ensure_period_open(tenant_id: uuid.UUID, on_date: date) -> None:
    period = period_of(on_date)
    stmt = pg_insert(AccountingPeriod).values(tenant_id=tenant_id, period=period, status="open").on_conflict_do_nothing(index_elements=["tenant_id", "period"])
    session.execute(stmt)


def require_open_period(tenant_id: uuid.UUID, on_date: date, action: str) -> None:
    period = period_of(on_date)
    row = AccountingPeriod.query.filter_by(tenant_id=tenant_id, period=period).first()
    assert_period_open(period, row.status if row else None, action)


# ---- AP -----------------------------------------------------------------


def find_ap_invoice(tenant_id: uuid.UUID, id: uuid.UUID) -> ApInvoice | None:
    return ApInvoice.query.filter_by(tenant_id=tenant_id, id=id).first()


def require_ap_invoice(tenant_id: uuid.UUID, id: uuid.UUID) -> ApInvoice:
    row = find_ap_invoice(tenant_id, id)
    if not row:
        raise not_found(f"Payable {id}")
    return row


def lock_ap_invoice(tenant_id: uuid.UUID, id: uuid.UUID) -> ApInvoice | None:
    return session.query(ApInvoice).filter_by(tenant_id=tenant_id, id=id).with_for_update().first()


def to_ap_api(row: ApInvoice) -> dict:
    pos = position(row.amount, row.paid_amount)  # AP has no credit_amount column - always reports "0" here
    return {
        "id": str(row.id),
        "number": row.number,
        "sourceType": row.source_type,
        "vendorInvoiceNo": row.vendor_invoice_no,
        "poId": str(row.po_id) if row.po_id else None,
        "poNumber": row.po_number,
        "grnId": str(row.grn_id) if row.grn_id else None,
        "vendorId": str(row.vendor_id),
        "vendorName": row.vendor_name,
        "invoiceDate": row.invoice_date.isoformat() if row.invoice_date else None,
        "dueDate": row.due_date.isoformat() if row.due_date else None,
        "period": row.period,
        "currency": row.currency,
        "taxAmount": decimal_str(row.tax_amount),
        "status": row.status,
        "matchStatus": row.match_status,
        "matchVariance": decimal_str(row.match_variance) if row.match_variance is not None else None,
        "matchNote": row.match_note,
        "notes": row.notes,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "amount": pos.amount,
        "paidAmount": pos.paid_amount,
        "creditAmount": pos.credit_amount,
        "outstanding": pos.outstanding,
        "settled": pos.settled,
        "aging": _aging_bucket(row.due_date, date.today(), row.status == "settled"),
    }


def to_ap_invoice_line_api(line: ApInvoiceLine) -> dict:
    return {
        "id": str(line.id),
        "lineNo": line.line_no,
        "poLineId": str(line.po_line_id) if line.po_line_id else None,
        "sku": line.sku,
        "description": line.description,
        "quantity": decimal_str(line.quantity) if line.quantity is not None else None,
        "uom": line.uom,
        "unitPrice": decimal_str(line.unit_price) if line.unit_price is not None else None,
        "amount": decimal_str(line.amount),
        "taxCode": line.tax_code,
        "taxAmount": decimal_str(line.tax_amount),
    }


def post_payable(
    tenant_id: uuid.UUID,
    *,
    source_type: str = "purchase",
    source_id: str | None = None,
    reference: str | None = None,
    po_id: uuid.UUID | None = None,
    po_number: str | None = None,
    grn_id: uuid.UUID | None = None,
    vendor_id: uuid.UUID,
    vendor_name: str = "Vendor",
    amount,
    tax_amount="0",
    currency: str,
    due_date: date,
    lines: list[dict] | None = None,
    actor_user_id: str | None = None,
) -> dict:
    """Direct-call equivalent of POST /internal/ap/invoices. Idempotent on
    (tenant_id, vendor_id, vendor_invoice_no) - vendor_invoice_no is
    `reference` if given, else the freshly generated (always-unique) number,
    which means a retry WITHOUT a stable reference will always double-post.
    Faithfully preserved, not fixed - callers that care about idempotency
    must supply a stable reference themselves (Logistics's call site does)."""
    number = next_document_number(tenant_id, settings.ap_number_prefix, pad=4, start=5500)
    match_status = "unmatched" if source_type == "purchase" else "not_applicable"
    vendor_invoice_no = reference or number
    # A plain-SQL on-conflict upsert, not an ORM add()+flush() - this may run
    # mid-way through a caller's own transaction (e.g. logistics.py's
    # create_logistics_invoice, after it has already flushed its own
    # LogisticsInvoice row), and a caught-exception-then-rollback() here
    # would discard that sibling work too, not just this insert.
    stmt = (
        pg_insert(ApInvoice)
        .values(
            tenant_id=tenant_id,
            number=number,
            source_type=source_type,
            source_id=source_id,
            vendor_invoice_no=vendor_invoice_no,
            po_id=po_id,
            po_number=po_number,
            grn_id=grn_id,
            vendor_id=vendor_id,
            vendor_name=vendor_name,
            due_date=due_date,
            period=period_of(date.today()),
            currency=currency,
            amount=to_decimal(amount),
            tax_amount=to_decimal(tax_amount),
            status="open",
            match_status=match_status,
            created_by="system",
        )
        .on_conflict_do_nothing(index_elements=["tenant_id", "vendor_id", "vendor_invoice_no"])
        .returning(ApInvoice.id)
    )
    result = session.execute(stmt).first()
    if result is None:
        existing = ApInvoice.query.filter_by(tenant_id=tenant_id, vendor_id=vendor_id, vendor_invoice_no=vendor_invoice_no).one()
        return {"status": "already-posted", "id": str(existing.id), "number": existing.number}
    return {"id": str(result[0]), "number": number}


def get_invoiced_qty_by_line(tenant_id: uuid.UUID, po_id: uuid.UUID) -> dict:
    """Direct-call equivalent of GET /internal/ap/invoiced. Never raises for
    an unknown poId - returns an empty byLineId, matching Node."""
    rows = (
        session.query(ApInvoiceLine.po_line_id, func.sum(ApInvoiceLine.quantity).label("qty"))
        .join(ApInvoice, ApInvoice.id == ApInvoiceLine.ap_invoice_id)
        .filter(ApInvoice.tenant_id == tenant_id, ApInvoice.po_id == po_id, ApInvoice.status != "cancelled", ApInvoiceLine.po_line_id.isnot(None))
        .group_by(ApInvoiceLine.po_line_id)
        .all()
    )
    return {"poId": str(po_id), "byLineId": {str(r.po_line_id): decimal_str(r.qty) for r in rows}}


# ---- AR -----------------------------------------------------------------


def find_ar_invoice(tenant_id: uuid.UUID, id: uuid.UUID) -> ArInvoice | None:
    return ArInvoice.query.filter_by(tenant_id=tenant_id, id=id).first()


def require_ar_invoice(tenant_id: uuid.UUID, id: uuid.UUID) -> ArInvoice:
    row = find_ar_invoice(tenant_id, id)
    if not row:
        raise not_found(f"Receivable {id}")
    return row


def lock_ar_invoice(tenant_id: uuid.UUID, id: uuid.UUID) -> ArInvoice | None:
    return session.query(ArInvoice).filter_by(tenant_id=tenant_id, id=id).with_for_update().first()


def to_ar_api(row: ArInvoice) -> dict:
    pos = position(row.amount, row.paid_amount, row.credit_amount)
    return {
        "id": str(row.id),
        "number": row.number,
        "orderId": str(row.order_id) if row.order_id else None,
        "orderNumber": row.order_number,
        "invoiceId": str(row.invoice_id) if row.invoice_id else None,
        "customerId": str(row.customer_id),
        "customerName": row.customer_name,
        "invoiceDate": row.invoice_date.isoformat() if row.invoice_date else None,
        "dueDate": row.due_date.isoformat() if row.due_date else None,
        "period": row.period,
        "currency": row.currency,
        "taxAmount": decimal_str(row.tax_amount),
        "status": row.status,
        "notes": row.notes,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "amount": pos.amount,
        "paidAmount": pos.paid_amount,
        "creditAmount": pos.credit_amount,
        "outstanding": pos.outstanding,
        "settled": pos.settled,
        "aging": _aging_bucket(row.due_date, date.today(), row.status == "settled"),
        "eInvoice": {"status": row.einvoice_status, "irn": row.irn, "ackNo": row.ack_no, "ackDate": row.ack_date.isoformat() if row.ack_date else None, "error": row.einvoice_error},
    }


def post_receivable(
    tenant_id: uuid.UUID,
    *,
    order_id: uuid.UUID | None = None,
    order_number: str | None = None,
    invoice_id: uuid.UUID | None = None,
    invoice_number: str,
    customer_id: uuid.UUID,
    customer_name: str = "Customer",
    amount,
    tax_amount="0",
    currency: str,
    due_date: date,
) -> dict:
    """Direct-call equivalent of POST /internal/ar/invoices (Order's
    postReceivable). invoice_number is used verbatim - AR invoices are never
    numbered by Finance. Node's real call site omits orderNumber/
    customerName/taxAmount entirely, so this landing on the "Customer"/"0"
    defaults for those fields whenever the caller does the same is faithful,
    not a bug to fix. Idempotent on (tenant_id, number)."""
    stmt = (
        pg_insert(ArInvoice)
        .values(
            tenant_id=tenant_id,
            number=invoice_number,
            order_id=order_id,
            order_number=order_number,
            invoice_id=invoice_id,
            customer_id=customer_id,
            customer_name=customer_name,
            due_date=due_date,
            period=period_of(date.today()),
            currency=currency,
            amount=to_decimal(amount),
            tax_amount=to_decimal(tax_amount),
            status="open",
        )
        .on_conflict_do_nothing(index_elements=["tenant_id", "number"])
        .returning(ArInvoice.id)
    )
    result = session.execute(stmt).first()
    if result is None:
        existing = ArInvoice.query.filter_by(tenant_id=tenant_id, number=invoice_number).one()
        return {"status": "already-posted", "id": str(existing.id), "number": existing.number}
    return {"id": str(result[0]), "number": invoice_number}


# ---- payments -------------------------------------------------------------


def find_payment(tenant_id: uuid.UUID, id: uuid.UUID) -> Payment | None:
    return Payment.query.filter_by(tenant_id=tenant_id, id=id).first()


def lock_payment(tenant_id: uuid.UUID, id: uuid.UUID) -> Payment | None:
    return session.query(Payment).filter_by(tenant_id=tenant_id, id=id).with_for_update().first()


def to_payment_api(row: Payment) -> dict:
    return {
        "id": str(row.id),
        "number": row.number,
        "direction": row.direction,
        "partyId": str(row.party_id),
        "partyName": row.party_name,
        "paymentDate": row.payment_date.isoformat() if row.payment_date else None,
        "method": row.method,
        "reference": row.reference,
        "currency": row.currency,
        "amount": decimal_str(row.amount),
        "unallocated": decimal_str(row.unallocated),
        "status": row.status,
        "approvedBy": row.approved_by,
        "gatewayProvider": row.gateway_provider,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }


# ---- aging (shared by AP + AR) --------------------------------------------


def _aging_bucket(due_date: date, as_of: date, settled: bool = False) -> str:
    if settled:
        return "current"
    days = (as_of - due_date).days
    if days <= 0:
        return "current"
    if days <= 30:
        return "0-30"
    if days <= 60:
        return "31-60"
    if days <= 90:
        return "61-90"
    return "90+"


def aging_report(rows: list, as_of: date, name_of, id_of) -> dict:
    """rows: ApInvoice or ArInvoice instances, pre-filtered by the caller to
    status in ('open','partially_paid'). Outstanding here is amount-paid_amount
    ONLY - it deliberately ignores credit_amount even for AR rows, unlike
    position() elsewhere, a real inconsistency preserved as-is."""
    buckets = {"current": to_decimal(0), "0-30": to_decimal(0), "31-60": to_decimal(0), "61-90": to_decimal(0), "90+": to_decimal(0)}
    total = to_decimal(0)
    by_party: dict[str, dict] = {}
    documents = []

    for row in rows:
        outstanding = to_decimal(row.amount) - to_decimal(row.paid_amount)
        if outstanding <= 0:
            continue
        bucket = _aging_bucket(row.due_date, as_of)
        buckets[bucket] += outstanding
        total += outstanding

        party_id = id_of(row)
        party_name = name_of(row)
        entry = by_party.setdefault(party_id, {"partyId": party_id, "partyName": party_name, "outstanding": to_decimal(0), "buckets": {k: to_decimal(0) for k in buckets}})
        entry["outstanding"] += outstanding
        entry["buckets"][bucket] += outstanding

        documents.append({"number": row.number, "partyName": party_name, "dueDate": row.due_date.isoformat(), "currency": row.currency, "amount": decimal_str(row.amount), "paidAmount": decimal_str(row.paid_amount), "outstanding": decimal_str(outstanding), "bucket": bucket})

    by_party_list = sorted(by_party.values(), key=lambda e: e["outstanding"], reverse=True)
    for e in by_party_list:
        e["outstanding"] = decimal_str(e["outstanding"])
        e["buckets"] = {k: decimal_str(v) for k, v in e["buckets"].items()}

    return {
        "asOf": as_of.isoformat(),
        "total": decimal_str(total),
        "buckets": {k: decimal_str(v) for k, v in buckets.items()},
        "byParty": by_party_list,
        "documents": documents,
    }


# ---- committed AR/AP - value that hasn't reached a real AP/AR invoice yet -
# a PO already issued to a vendor but not yet GRN'd (future payable), and an
# order already confirmed but not yet allocated (future receivable). Neither
# side has posted anything to ApInvoice/ArInvoice yet - that only happens at
# GRN receipt / order invoicing respectively - so this reads PurchaseOrder/
# PoLine and Order/OrderLine directly instead of those tables. ------------


def _committed_ap(tenant_id: uuid.UUID) -> dict:
    pos = PurchaseOrder.query.filter(PurchaseOrder.tenant_id == tenant_id, PurchaseOrder.status.in_(("issued", "partially_received"))).all()
    lines_by_po: dict[uuid.UUID, list[PoLine]] = {}
    if pos:
        for line in PoLine.query.filter(PoLine.po_id.in_([p.id for p in pos]), PoLine.status != "cancelled").all():
            lines_by_po.setdefault(line.po_id, []).append(line)

    total = to_decimal(0)
    by_vendor: dict[str, dict] = {}
    documents = []
    for po in pos:
        committed = to_decimal(0)
        for line in lines_by_po.get(po.id, []):
            open_qty = to_decimal(line.quantity) - to_decimal(line.received_qty) - to_decimal(line.rejected_qty)
            if open_qty > 0:
                committed += open_qty * to_decimal(line.unit_price)
        if committed <= 0:
            continue
        total += committed
        vendor_id = str(po.vendor_id)
        entry = by_vendor.setdefault(vendor_id, {"vendorId": vendor_id, "vendorName": po.vendor_name, "committed": to_decimal(0)})
        entry["committed"] += committed
        documents.append(
            {
                "number": po.number,
                "vendorName": po.vendor_name,
                "status": po.status,
                "poDate": po.po_date.isoformat() if po.po_date else None,
                "expectedDate": po.expected_date.isoformat() if po.expected_date else None,
                "currency": po.currency,
                "committed": decimal_str(committed),
            }
        )

    by_vendor_list = sorted(by_vendor.values(), key=lambda e: e["committed"], reverse=True)
    for e in by_vendor_list:
        e["committed"] = decimal_str(e["committed"])
    documents.sort(key=lambda d: d["poDate"] or "", reverse=True)
    return {"total": decimal_str(total), "byVendor": by_vendor_list, "documents": documents}


def _committed_ar(tenant_id: uuid.UUID) -> dict:
    orders = Order.query.filter(Order.tenant_id == tenant_id, Order.status.in_(("confirmed", "partially_allocated"))).all()
    lines_by_order: dict[uuid.UUID, list[OrderLine]] = {}
    if orders:
        for line in OrderLine.query.filter(OrderLine.order_id.in_([o.id for o in orders]), OrderLine.status != "cancelled").all():
            lines_by_order.setdefault(line.order_id, []).append(line)

    total = to_decimal(0)
    by_customer: dict[str, dict] = {}
    documents = []
    for order in orders:
        committed = to_decimal(0)
        for line in lines_by_order.get(order.id, []):
            open_qty = to_decimal(line.quantity) - to_decimal(line.allocated_qty)
            if open_qty > 0:
                committed += open_qty * to_decimal(line.unit_price)
        if committed <= 0:
            continue
        total += committed
        customer_id = str(order.customer_id)
        entry = by_customer.setdefault(customer_id, {"customerId": customer_id, "customerName": order.customer_name, "committed": to_decimal(0)})
        entry["committed"] += committed
        documents.append(
            {
                "number": order.number,
                "customerName": order.customer_name,
                "status": order.status,
                "orderDate": order.order_date.isoformat() if order.order_date else None,
                "promisedDate": order.promised_date.isoformat() if order.promised_date else None,
                "currency": order.currency,
                "committed": decimal_str(committed),
            }
        )

    by_customer_list = sorted(by_customer.values(), key=lambda e: e["committed"], reverse=True)
    for e in by_customer_list:
        e["committed"] = decimal_str(e["committed"])
    documents.sort(key=lambda d: d["orderDate"] or "", reverse=True)
    return {"total": decimal_str(total), "byCustomer": by_customer_list, "documents": documents}


def committed_report(tenant_id: uuid.UUID, as_of: date) -> dict:
    """Future AP: purchase orders issued to a vendor but not yet GRN'd (the
    open quantity on each line, at PO unit price) - the moment a GRN posts,
    that quantity leaves this report and (once invoiced) becomes a real
    ApInvoice. Future AR: sales orders confirmed but not yet allocated
    (same open-quantity math against OrderLine) - the moment a line is
    allocated it leaves this report, and becomes a real ArInvoice once the
    order is invoiced. Neither side is booked anywhere yet, which is exactly
    why this can't be read off ApInvoice/ArInvoice like aging_report()."""
    return {"asOf": as_of.isoformat(), "ap": _committed_ap(tenant_id), "ar": _committed_ar(tenant_id)}


# ---- reporting.ts (working capital) ----------------------------------------


def working_capital_report(tenant_id: uuid.UUID, as_of_d: date, warehouse_id: str | None = None, months: int = 6, precomputed_valuation: dict | None = None) -> dict:
    """Extracted from GET /working-capital so the analytics dashboard can call
    it in-process too - same pattern as inventory_ledger.compute_valuation()
    being callable directly by both /inventory/valuation and this report.

    `precomputed_valuation`: the dashboard already computes an unscoped
    valuation for its own inventory panel, so it passes that result through
    here instead of making this function recompute the same full
    stock_ledger scan a second time. Callers with a warehouse_id (the
    standalone /working-capital route) always compute their own, since a
    dashboard-wide valuation wouldn't be scoped to that warehouse.
    """
    from app.services import inventory_ledger

    ar_rows = ArInvoice.query.filter(ArInvoice.tenant_id == tenant_id, ArInvoice.status.in_(("open", "partially_paid"))).all()
    ar_outstanding = sum((to_decimal(r.amount) - to_decimal(r.paid_amount) - to_decimal(r.credit_amount) for r in ar_rows), to_decimal(0))
    ar_overdue = sum((to_decimal(r.amount) - to_decimal(r.paid_amount) - to_decimal(r.credit_amount) for r in ar_rows if r.due_date < as_of_d), to_decimal(0))

    ap_rows = ApInvoice.query.filter(ApInvoice.tenant_id == tenant_id, ApInvoice.status.in_(("open", "partially_paid"))).all()
    ap_outstanding = sum((to_decimal(r.amount) - to_decimal(r.paid_amount) for r in ap_rows), to_decimal(0))
    ap_overdue = sum((to_decimal(r.amount) - to_decimal(r.paid_amount) for r in ap_rows if r.due_date < as_of_d), to_decimal(0))

    if precomputed_valuation is not None and warehouse_id is None:
        valuation = precomputed_valuation
        inventory_available = True
        inventory_value = to_decimal(valuation["totalValue"])
        incomplete_reason = None
    else:
        try:
            valuation = inventory_ledger.compute_valuation(tenant_id, warehouse_id)
            inventory_available = True
            inventory_value = to_decimal(valuation["totalValue"])
            incomplete_reason = None
        except Exception:  # noqa: BLE001
            inventory_available = False
            inventory_value = to_decimal(0)
            incomplete_reason = "The inventory service could not be reached to compute inventory value"

    working_capital_value = inventory_value + ar_outstanding - ap_outstanding

    current_period = period_of(as_of_d)
    trend = []
    year, month_num = as_of_d.year, as_of_d.month
    for i in range(months - 1, -1, -1):
        m = month_num - i
        y = year
        while m <= 0:
            m += 12
            y -= 1
        month_str = f"{y:04d}-{m:02d}"
        ar_for_month = sum((to_decimal(r.amount) - to_decimal(r.paid_amount) - to_decimal(r.credit_amount) for r in ar_rows if r.period <= month_str), to_decimal(0))
        ap_for_month = sum((to_decimal(r.amount) - to_decimal(r.paid_amount) for r in ap_rows if r.period <= month_str), to_decimal(0))
        trend.append({"month": month_str, "inventory": decimal_str(inventory_value) if month_str == current_period and inventory_available else None, "ar": decimal_str(ar_for_month), "ap": decimal_str(ap_for_month)})

    return {
        "asOf": as_of_d.isoformat(),
        "currency": "INR",
        "workingCapital": decimal_str(working_capital_value),
        "complete": inventory_available,
        "incompleteReason": incomplete_reason,
        "components": {"inventoryValue": decimal_str(inventory_value), "accountsReceivable": decimal_str(ar_outstanding), "accountsPayable": decimal_str(ap_outstanding)},
        "receivables": {"outstanding": decimal_str(ar_outstanding), "overdue": decimal_str(ar_overdue), "openInvoices": len(ar_rows)},
        "payables": {"outstanding": decimal_str(ap_outstanding), "overdue": decimal_str(ap_overdue), "openInvoices": len(ap_rows)},
        "trend": trend,
    }
