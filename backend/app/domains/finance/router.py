"""Finance: AP/AR invoices, payments, credit notes, aging, committed-spend
and working-capital reports. Ported 1:1 (behavior) from
backend_py/app/routes/finance.py (itself a merge of the original's
ap/ar/payments/reporting route files - they share one auth model and are
cross-coupled).

The original's three unguarded /internal/* endpoints (ap/invoices,
ap/invoiced, ar/invoices) are plain functions in finance_repo.py that
orders/logistics call directly, never routes here. Several real quirks of
the original are preserved deliberately and called out inline (AR credit
notes always settling the invoice, reversal not accounting for credit
amounts, approve-payment not applying allocations).

Route order matters: /ap/aging, /ar/aging are registered before /ap/{id},
/ar/{id} so the literal path isn't captured as an id.
"""

from __future__ import annotations

import uuid as uuid_mod
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, or_

from app.core.access_scope import assert_warehouse_in_scope
from app.core.audit import audit
from app.core.auth import Actor, require_permission
from app.core.config import settings
from app.core.db import session
from app.core.errors import conflict, not_found, rule_violation
from app.core.idempotency import get_raw_body, run_idempotent
from app.core.money import decimal_str, to_decimal
from app.core.pagination import ListQuery, list_response, offset_of
from app.domains.finance.schemas import ApInvoiceBody, CreditNoteBody, PaymentBody, ReasonBody
from app.models.ap_invoice import ApInvoice
from app.models.ap_invoice_line import ApInvoiceLine
from app.models.ar_invoice import ArInvoice
from app.models.credit_note import CreditNote
from app.models.payment import Payment
from app.models.payment_allocation import PaymentAllocation
from app.services import finance_repo, order_repo, procurement_repo
from app.services.finance_periods import period_of
from app.services.finance_settlement import assert_allocations_valid, requires_payment_approval
from app.services.finance_three_way_match import MatchLine, assert_match_approved, three_way_match
from app.services.party_repo import apply_credit_usage_for_party
from app.services.sequences import next_document_number

router = APIRouter(prefix="/api/v1", tags=["finance"])


def _statuses(status: str | None) -> list[str]:
    return [s.strip() for s in (status or "").split(",") if s.strip()]


# ---- AP ------------------------------------------------------------------


@router.get("/ap")
def list_ap(
    actor: Actor = Depends(require_permission("finance:read")),
    query: ListQuery = Depends(),
    status: str | None = None,
    vendorId: uuid_mod.UUID | None = None,
    overdueOnly: bool = False,
):
    q = ApInvoice.query.filter(ApInvoice.tenant_id == actor["tenant_id"])
    if status:
        statuses = _statuses(status)
        if statuses:
            q = q.filter(ApInvoice.status.in_(statuses))
    else:
        q = q.filter(ApInvoice.status != "cancelled")
    if vendorId:
        q = q.filter(ApInvoice.vendor_id == vendorId)
    if overdueOnly:
        q = q.filter(ApInvoice.due_date < date.today(), ApInvoice.status != "settled")
    if query.q:
        like = f"%{query.q}%"
        q = q.filter(or_(ApInvoice.number.ilike(like), ApInvoice.vendor_name.ilike(like), ApInvoice.po_number.ilike(like)))

    total = q.count()
    rows = q.order_by(ApInvoice.due_date.asc()).limit(query.limit).offset(offset_of(query)).all()
    return list_response([finance_repo.to_ap_api(r) for r in rows], query, total)


@router.get("/ap/aging")
def ap_aging(actor: Actor = Depends(require_permission("finance:read")), asOf: date | None = None, vendorId: uuid_mod.UUID | None = None):
    as_of_d = asOf or date.today()
    q = ApInvoice.query.filter(ApInvoice.tenant_id == actor["tenant_id"], ApInvoice.status.in_(("open", "partially_paid")))
    if vendorId:
        q = q.filter(ApInvoice.vendor_id == vendorId)
    rows = q.order_by(ApInvoice.due_date.asc()).all()
    return finance_repo.aging_report(rows, as_of_d, lambda r: r.vendor_name, lambda r: str(r.vendor_id))


@router.get("/ap/{id}")
def get_ap(id: uuid_mod.UUID, actor: Actor = Depends(require_permission("finance:read"))):
    row = finance_repo.require_ap_invoice(actor["tenant_id"], id)
    lines = ApInvoiceLine.query.filter_by(ap_invoice_id=id).order_by(ApInvoiceLine.line_no).all()
    payments = (
        session.query(PaymentAllocation.amount, Payment.number, Payment.payment_date, Payment.method, Payment.status)
        .join(Payment, Payment.id == PaymentAllocation.payment_id)
        .filter(PaymentAllocation.ap_invoice_id == id)
        .all()
    )
    resp = finance_repo.to_ap_api(row)
    resp["lines"] = [finance_repo.to_ap_invoice_line_api(l) for l in lines]
    resp["payments"] = [{"amount": decimal_str(p.amount), "number": p.number, "paymentDate": p.payment_date.isoformat(), "method": p.method, "status": p.status} for p in payments]
    return resp


@router.get("/ap/{id}/match")
def ap_match(id: uuid_mod.UUID, actor: Actor = Depends(require_permission("finance:read"))):
    row = finance_repo.require_ap_invoice(actor["tenant_id"], id)
    return {
        "apInvoiceId": str(row.id),
        "number": row.number,
        "poId": str(row.po_id) if row.po_id else None,
        "matchStatus": row.match_status,
        "variance": decimal_str(row.match_variance) if row.match_variance is not None else None,
        "note": row.match_note,
    }


@router.post("/ap/invoices", status_code=201)
def post_ap_invoice(body: ApInvoiceBody, request: Request, raw_body: bytes = Depends(get_raw_body), actor: Actor = Depends(require_permission("invoice:post"))):
    tenant_id = actor["tenant_id"]

    def _do():
        invoice_date = body.invoiceDate or date.today()
        due_date = body.dueDate or (invoice_date + timedelta(days=30))
        finance_repo.require_open_period(tenant_id, invoice_date, "a vendor invoice")

        existing = ApInvoice.query.filter_by(tenant_id=tenant_id, vendor_id=body.vendorId, vendor_invoice_no=body.vendorInvoiceNo).first()
        if existing:
            raise conflict(f"{body.vendorInvoiceNo} has already been posted for this vendor as {existing.number}", code="DUPLICATE_VENDOR_INVOICE")

        po_number = None
        match = three_way_match([], settings.finance_match_tolerance_percent)
        if body.poId:
            po = procurement_repo.get_receivable_po(tenant_id, body.poId)
            if not po:
                raise not_found(f"Purchase order {body.poId}")
            po_number = po["number"]
            po_lines_by_id = {l["id"]: l for l in po["lines"]}
            match_lines = []
            for line in body.lines:
                if not line.poLineId or str(line.poLineId) not in po_lines_by_id:
                    continue
                po_line = po_lines_by_id[str(line.poLineId)]
                match_lines.append(
                    MatchLine(
                        po_line_id=str(line.poLineId),
                        sku=po_line["sku"],
                        ordered_qty=po_line["orderedQty"],
                        unit_price=po_line["unitPrice"],
                        received_qty=po_line["receivedQty"],
                        invoiced_qty=line.quantity or "0",
                        invoiced_unit_price=line.unitPrice or "0",
                    )
                )
            match = three_way_match(match_lines, settings.finance_match_tolerance_percent)
            assert_match_approved(match, body.vendorInvoiceNo, body.varianceReason)

        number = next_document_number(tenant_id, settings.ap_number_prefix, pad=4, start=5500)
        invoice = ApInvoice(
            tenant_id=tenant_id,
            number=number,
            source_type="purchase",
            vendor_invoice_no=body.vendorInvoiceNo,
            po_id=body.poId,
            po_number=po_number,
            grn_id=body.grnId,
            vendor_id=body.vendorId,
            vendor_name=body.vendorName or "Vendor",
            invoice_date=invoice_date,
            due_date=due_date,
            period=period_of(invoice_date),
            currency=body.currency or settings.base_currency,
            amount=to_decimal(body.amount),
            tax_amount=to_decimal(body.taxAmount),
            status="open",
            match_status=match.status,
            match_variance=to_decimal(match.variance) if body.poId else None,
            match_note="; ".join(match.issues) or None,
            approved_by=str(actor["user_id"]),
            approved_at=func.now(),
            notes=body.notes,
            created_by=str(actor["user_id"]),
        )
        session.add(invoice)
        session.flush()

        for i, line in enumerate(body.lines):
            session.add(
                ApInvoiceLine(
                    tenant_id=tenant_id,
                    ap_invoice_id=invoice.id,
                    line_no=i + 1,
                    po_line_id=line.poLineId,
                    sku=line.sku,
                    description=line.description,
                    quantity=to_decimal(line.quantity) if line.quantity is not None else None,
                    uom=line.uom,
                    unit_price=to_decimal(line.unitPrice) if line.unitPrice is not None else None,
                    amount=to_decimal(line.amount),
                    tax_code=line.taxCode,
                    tax_amount=to_decimal(line.taxAmount),
                )
            )

        audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="ap.invoice.posted", entity_type="ap-invoice", entity_id=str(invoice.id), meta={"number": number, "matchStatus": match.status})
        session.commit()

        return 201, {"id": str(invoice.id), "number": number, "dueDate": due_date.isoformat(), "matchStatus": match.status, "matchVariance": match.variance, "issues": match.issues}

    status_code, response_body = run_idempotent(request.headers.get("Idempotency-Key"), "POST", request.url.path, raw_body, actor, _do)
    return JSONResponse(status_code=status_code, content=response_body)


# ---- AR ------------------------------------------------------------------


@router.get("/ar")
def list_ar(
    actor: Actor = Depends(require_permission("finance:read")),
    query: ListQuery = Depends(),
    status: str | None = None,
    customerId: uuid_mod.UUID | None = None,
):
    q = ArInvoice.query.filter(ArInvoice.tenant_id == actor["tenant_id"])
    if status:
        statuses = _statuses(status)
        if statuses:
            q = q.filter(ArInvoice.status.in_(statuses))
    else:
        q = q.filter(ArInvoice.status != "cancelled")
    if customerId:
        q = q.filter(ArInvoice.customer_id == customerId)
    if query.q:
        like = f"%{query.q}%"
        q = q.filter(or_(ArInvoice.number.ilike(like), ArInvoice.customer_name.ilike(like), ArInvoice.order_number.ilike(like)))

    total = q.count()
    rows = q.order_by(ArInvoice.due_date.asc()).limit(query.limit).offset(offset_of(query)).all()
    return list_response([finance_repo.to_ar_api(r) for r in rows], query, total)


@router.get("/ar/aging")
def ar_aging(actor: Actor = Depends(require_permission("finance:read")), asOf: date | None = None, customerId: uuid_mod.UUID | None = None):
    as_of_d = asOf or date.today()
    q = ArInvoice.query.filter(ArInvoice.tenant_id == actor["tenant_id"], ArInvoice.status.in_(("open", "partially_paid")))
    if customerId:
        q = q.filter(ArInvoice.customer_id == customerId)
    rows = q.order_by(ArInvoice.due_date.asc()).all()
    return finance_repo.aging_report(rows, as_of_d, lambda r: r.customer_name, lambda r: str(r.customer_id))


@router.get("/ar/{id}")
def get_ar(id: uuid_mod.UUID, actor: Actor = Depends(require_permission("finance:read"))):
    row = finance_repo.require_ar_invoice(actor["tenant_id"], id)
    payments = (
        session.query(PaymentAllocation.amount, Payment.number, Payment.payment_date, Payment.method, Payment.status, Payment.reference)
        .join(Payment, Payment.id == PaymentAllocation.payment_id)
        .filter(PaymentAllocation.ar_invoice_id == id)
        .all()
    )
    resp = finance_repo.to_ar_api(row)
    resp["payments"] = [{"amount": decimal_str(p.amount), "number": p.number, "paymentDate": p.payment_date.isoformat(), "method": p.method, "status": p.status, "reference": p.reference} for p in payments]
    return resp


@router.get("/finance/committed")
def committed(actor: Actor = Depends(require_permission("finance:read")), asOf: date | None = None):
    """Future AP (issued POs not yet GRN'd) and future AR (confirmed orders
    not yet allocated) - value neither side has posted to ApInvoice/
    ArInvoice yet, so it never shows up in /ap, /ar, or the aging reports."""
    return finance_repo.committed_report(actor["tenant_id"], asOf or date.today())


@router.post("/credit-notes", status_code=201)
def create_credit_note(body: CreditNoteBody, actor: Actor = Depends(require_permission("payment:approve"))):
    tenant_id = actor["tenant_id"]

    if bool(body.arInvoiceId) == bool(body.apInvoiceId):
        raise rule_violation("Exactly one of arInvoiceId or apInvoiceId must be given", code="CREDIT_NOTE_TARGET_INVALID")

    finance_repo.require_open_period(tenant_id, date.today(), "a credit note")
    amount_d = to_decimal(body.amount)

    ar_invoice = None
    ap_invoice = None
    if body.arInvoiceId:
        ar_invoice = finance_repo.lock_ar_invoice(tenant_id, body.arInvoiceId)
        if not ar_invoice:
            raise not_found(f"Receivable {body.arInvoiceId}")
        outstanding = to_decimal(ar_invoice.amount) - to_decimal(ar_invoice.paid_amount) - to_decimal(ar_invoice.credit_amount)
        if amount_d > outstanding:
            raise rule_violation(f"Credit note {decimal_str(amount_d)} exceeds the outstanding balance {decimal_str(outstanding)}", code="CREDIT_NOTE_EXCEEDS_OUTSTANDING")
    else:
        ap_invoice = finance_repo.lock_ap_invoice(tenant_id, body.apInvoiceId)
        if not ap_invoice:
            raise not_found(f"Payable {body.apInvoiceId}")

    number = next_document_number(tenant_id, settings.cn_number_prefix, pad=4, start=1000)
    note = CreditNote(
        tenant_id=tenant_id,
        number=number,
        direction=body.direction,
        party_id=body.partyId,
        party_name=body.partyName or "Party",
        ar_invoice_id=body.arInvoiceId,
        ap_invoice_id=body.apInvoiceId,
        amount=amount_d,
        currency=body.currency or settings.base_currency,
        period=period_of(date.today()),
        reason=body.reason,
        approved_by=str(actor["user_id"]),
        approved_at=func.now(),
        status="applied",
        created_by=str(actor["user_id"]),
    )
    session.add(note)
    session.flush()

    if ar_invoice is not None:
        ar_invoice.credit_amount = to_decimal(ar_invoice.credit_amount) + amount_d
        if (to_decimal(ar_invoice.paid_amount) + to_decimal(ar_invoice.credit_amount) + amount_d) >= to_decimal(ar_invoice.amount):
            ar_invoice.status = "settled"
    else:
        ap_invoice.amount = max(to_decimal(ap_invoice.amount) - amount_d, to_decimal(0))

    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="finance.credit_note.issued", entity_type="credit-note", entity_id=str(note.id), reason=body.reason, meta={"number": number, "amount": decimal_str(amount_d)})
    session.commit()

    return {"id": str(note.id), "number": number}


# ---- payments --------------------------------------------------------------


@router.get("/payments")
def list_payments(
    actor: Actor = Depends(require_permission("finance:read")),
    query: ListQuery = Depends(),
    direction: str | None = None,
    partyId: uuid_mod.UUID | None = None,
    status: str | None = None,
):
    q = Payment.query.filter(Payment.tenant_id == actor["tenant_id"])
    if direction:
        q = q.filter(Payment.direction == direction)
    if partyId:
        q = q.filter(Payment.party_id == partyId)
    if status:
        q = q.filter(Payment.status == status)
    if query.q:
        like = f"%{query.q}%"
        q = q.filter(or_(Payment.number.ilike(like), Payment.party_name.ilike(like), Payment.reference.ilike(like)))

    total = q.count()
    rows = q.order_by(Payment.payment_date.desc(), Payment.created_at.desc()).limit(query.limit).offset(offset_of(query)).all()
    return list_response([finance_repo.to_payment_api(r) for r in rows], query, total)


def _record_payment(actor: Actor, body: PaymentBody, direction: str) -> tuple[int, dict]:
    tenant_id = actor["tenant_id"]
    payment_date = body.paymentDate or date.today()
    action = "a customer receipt" if direction == "inbound" else "a vendor payment"
    finance_repo.require_open_period(tenant_id, payment_date, action)

    model = ArInvoice if direction == "inbound" else ApInvoice
    fk_field = "ar_invoice_id" if direction == "inbound" else "ap_invoice_id"

    # Lock every target invoice up front, sorted by id ascending - a fixed
    # lock order regardless of request order, avoiding deadlocks against a
    # concurrent payment touching an overlapping invoice set.
    invoice_ids = sorted({str(a.invoiceId) for a in body.allocations})
    invoices: dict[str, object] = {}
    for iid in invoice_ids:
        row = session.query(model).filter_by(tenant_id=tenant_id, id=iid).with_for_update().first()
        if not row:
            raise not_found(f"{'Payable' if direction == 'outbound' else 'Receivable'} {iid}")
        if row.status == "cancelled":
            raise rule_violation(f"{row.number} is cancelled and cannot be paid", code="INVOICE_CANCELLED")
        invoices[iid] = row

    allocation_inputs = []
    for a in body.allocations:
        row = invoices[str(a.invoiceId)]
        credit = to_decimal(row.credit_amount) if direction == "inbound" else to_decimal(0)
        outstanding = to_decimal(row.amount) - to_decimal(row.paid_amount) - credit
        allocation_inputs.append({"invoiceNumber": row.number, "requested": a.amount, "outstanding": decimal_str(outstanding)})

    summary = assert_allocations_valid(payment_amount=body.amount, allocations=allocation_inputs, overpayment_policy=settings.overpayment_policy, direction=direction)

    needs_approval = direction == "outbound" and requires_payment_approval(body.amount, settings.payment_approval_threshold)
    number = next_document_number(tenant_id, settings.pay_number_prefix, pad=4, start=1000)
    payment = Payment(
        tenant_id=tenant_id,
        number=number,
        direction=direction,
        party_id=body.partyId,
        party_name=body.partyName or "Party",
        payment_date=payment_date,
        period=period_of(payment_date),
        method=body.method,
        reference=body.reference,
        currency=body.currency or settings.base_currency,
        exchange_rate=to_decimal(body.exchangeRate),
        amount=to_decimal(body.amount),
        unallocated=to_decimal(summary.unallocated),
        status="pending_approval" if needs_approval else "posted",
        notes=body.notes,
        created_by=str(actor["user_id"]),
    )
    session.add(payment)
    session.flush()

    settled_numbers = []
    settled_invoices_for_downstream = []
    for a in body.allocations:
        row = invoices[str(a.invoiceId)]
        session.add(PaymentAllocation(tenant_id=tenant_id, payment_id=payment.id, **{fk_field: row.id}, amount=to_decimal(a.amount)))
        if needs_approval:
            # Allocations are recorded, but invoice balances are NOT updated
            # for a payment awaiting approval - matching the original's real
            # gap: /payments/{id}/approve only flips the payment's own status
            # and never goes back to apply these allocations.
            continue

        credit = to_decimal(row.credit_amount) if direction == "inbound" else to_decimal(0)
        outstanding_before = to_decimal(row.amount) - to_decimal(row.paid_amount) - credit
        row.paid_amount = to_decimal(row.paid_amount) + to_decimal(a.amount)
        fully = (outstanding_before - to_decimal(a.amount)) <= 0
        row.status = "settled" if fully else "partially_paid"
        if fully:
            settled_numbers.append(row.number)
            settled_invoices_for_downstream.append(row)

    audit(
        tenant_id=tenant_id,
        actor_id=actor["user_id"],
        actor_email=actor["email"],
        action=f"finance.{'ar' if direction == 'inbound' else 'ap'}.payment",
        entity_type="payment",
        entity_id=str(payment.id),
        meta={"number": number, "overpayments": [{"invoiceNumber": o.invoice_number, "excess": o.excess} for o in summary.overpayments]},
    )

    # Direct-call consistency upgrade (no network hop to swallow a failure
    # over) - only for a non-approval-blocked inbound payment, only for
    # invoices tied to an order.
    if direction == "inbound" and not needs_approval:
        for row in settled_invoices_for_downstream:
            if row.order_id:
                order_repo.apply_settlement(tenant_id, row.order_id, paid_to_date=row.paid_amount, invoice_total=row.amount)
                apply_credit_usage_for_party(tenant_id, row.customer_id, delta=decimal_str(to_decimal(0) - to_decimal(row.amount)), reference=f"{number} settled")

    session.commit()

    return 201, {
        "paymentId": str(payment.id),
        "number": number,
        "status": payment.status,
        "allocated": summary.total_allocated,
        "unallocated": summary.unallocated,
        "overpayments": [{"invoiceNumber": o.invoice_number, "excess": o.excess} for o in summary.overpayments],
        "settledInvoices": settled_numbers,
    }


@router.post("/ap/payments", status_code=201)
def record_ap_payment(body: PaymentBody, request: Request, raw_body: bytes = Depends(get_raw_body), actor: Actor = Depends(require_permission("payment:write"))):
    status_code, response_body = run_idempotent(request.headers.get("Idempotency-Key"), "POST", request.url.path, raw_body, actor, lambda: _record_payment(actor, body, "outbound"))
    return JSONResponse(status_code=status_code, content=response_body)


@router.post("/ar/payments", status_code=201)
def record_ar_payment(body: PaymentBody, request: Request, raw_body: bytes = Depends(get_raw_body), actor: Actor = Depends(require_permission("payment:write"))):
    status_code, response_body = run_idempotent(request.headers.get("Idempotency-Key"), "POST", request.url.path, raw_body, actor, lambda: _record_payment(actor, body, "inbound"))
    return JSONResponse(status_code=status_code, content=response_body)


@router.post("/payments/{id}/reverse")
def reverse_payment(id: uuid_mod.UUID, body: ReasonBody, actor: Actor = Depends(require_permission("payment:approve"))):
    tenant_id = actor["tenant_id"]
    finance_repo.require_open_period(tenant_id, date.today(), "a payment reversal")

    original = finance_repo.lock_payment(tenant_id, id)
    if not original:
        raise not_found(f"Payment {id}")
    if original.status == "reversed":
        raise conflict(f"{original.number} has already been reversed", code="PAYMENT_ALREADY_REVERSED")

    number = next_document_number(tenant_id, settings.pay_number_prefix, pad=4, start=1000)
    reversal = Payment(
        tenant_id=tenant_id,
        number=number,
        direction=original.direction,
        party_id=original.party_id,
        party_name=original.party_name,
        payment_date=date.today(),
        period=period_of(date.today()),
        method="adjustment",
        reference=f"Reversal of {original.number}",
        currency=original.currency,
        amount=to_decimal(0) - to_decimal(original.amount),
        status="posted",
        reverses_id=original.id,
        reversal_reason=body.reason,
        created_by=str(actor["user_id"]),
    )
    session.add(reversal)
    session.flush()

    # Lock target invoices in a fixed order (ascending id), same as
    # _record_payment above - a reversal touching the same invoice set as a
    # concurrent payment/reversal could otherwise deadlock.
    original_allocations = sorted(PaymentAllocation.query.filter_by(payment_id=original.id).all(), key=lambda a: str(a.ar_invoice_id or a.ap_invoice_id))
    for alloc in original_allocations:
        model = ArInvoice if alloc.ar_invoice_id else ApInvoice
        target_id = alloc.ar_invoice_id or alloc.ap_invoice_id
        row = session.query(model).filter_by(id=target_id).with_for_update().first()
        if row:
            row.paid_amount = max(to_decimal(row.paid_amount) - to_decimal(alloc.amount), to_decimal(0))
            credit = to_decimal(row.credit_amount) if alloc.ar_invoice_id else to_decimal(0)
            if to_decimal(row.paid_amount) + credit >= to_decimal(row.amount):
                row.status = "settled"
            elif to_decimal(row.paid_amount) + credit <= 0:
                row.status = "open"
            else:
                row.status = "partially_paid"
        fk_field = "ar_invoice_id" if alloc.ar_invoice_id else "ap_invoice_id"
        session.add(PaymentAllocation(tenant_id=tenant_id, payment_id=reversal.id, **{fk_field: target_id}, amount=to_decimal(0) - to_decimal(alloc.amount)))

    original.status = "reversed"
    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="finance.payment.reversed", entity_type="payment", entity_id=str(id), reason=body.reason, meta={"reversalNumber": number})
    session.commit()

    return {"paymentId": str(id), "reversalId": str(reversal.id), "reversalNumber": number, "status": "reversed"}


@router.post("/payments/{id}/approve")
def approve_payment(id: uuid_mod.UUID, actor: Actor = Depends(require_permission("payment:approve"))):
    tenant_id = actor["tenant_id"]
    payment = finance_repo.lock_payment(tenant_id, id)
    if not payment:
        raise not_found(f"Payment {id}")
    if payment.status != "pending_approval":
        raise conflict(f"{payment.number} is not pending approval", code="PAYMENT_NOT_PENDING")
    if payment.created_by == str(actor["user_id"]):
        raise rule_violation("You cannot approve a payment you recorded yourself", code="SELF_APPROVAL_BLOCKED")

    payment.status = "posted"
    payment.approved_by = str(actor["user_id"])
    payment.approved_at = func.now()

    allocations = PaymentAllocation.query.filter_by(payment_id=payment.id).all()
    for alloc in allocations:
        model = ArInvoice if alloc.ar_invoice_id else ApInvoice
        target_id = alloc.ar_invoice_id or alloc.ap_invoice_id
        row = session.query(model).filter_by(id=target_id).with_for_update().first()
        if row:
            credit = to_decimal(row.credit_amount) if alloc.ar_invoice_id else to_decimal(0)
            outstanding_before = to_decimal(row.amount) - to_decimal(row.paid_amount) - credit
            row.paid_amount = to_decimal(row.paid_amount) + to_decimal(alloc.amount)
            fully = (outstanding_before - to_decimal(alloc.amount)) <= 0
            row.status = "settled" if fully else "partially_paid"
    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="finance.payment.approved", entity_type="payment", entity_id=str(id))
    session.commit()

    return finance_repo.to_payment_api(payment)


# ---- reporting -----------------------------------------------------------


@router.get("/working-capital")
def working_capital(
    actor: Actor = Depends(require_permission("finance:read")),
    asOf: date | None = None,
    warehouseId: uuid_mod.UUID | None = None,
    months: int = 6,
):
    tenant_id = actor["tenant_id"]
    as_of_d = asOf or date.today()
    months = min(max(months, 1), 24)
    warehouse_id = warehouseId
    if warehouse_id:
        assert_warehouse_in_scope(actor, warehouse_id)
    elif actor["warehouse_ids"] is not None:
        warehouse_id = actor["warehouse_ids"]

    return finance_repo.working_capital_report(tenant_id, as_of_d, warehouse_id, months)


@router.get("/working-capital/cycle")
def working_capital_cycle(actor: Actor = Depends(require_permission("finance:read"))):
    tenant_id = actor["tenant_id"]
    cutoff = date.today() - timedelta(days=180)

    # Not filtered to status<>'cancelled' - cancelled invoices' invoice_date
    # still counts toward the average, matching the original exactly.
    ar_rows = session.query(ArInvoice.id, ArInvoice.invoice_date).filter(ArInvoice.tenant_id == tenant_id, ArInvoice.invoice_date >= cutoff).all()
    ap_rows = session.query(ApInvoice.id, ApInvoice.invoice_date).filter(ApInvoice.tenant_id == tenant_id, ApInvoice.invoice_date >= cutoff).all()

    def _payment_dates(rows, fk_column) -> dict:
        """Latest allocation's payment_date per invoice, in one joined query.
        Ascending order means the last row written per invoice is the newest
        allocation."""
        if not rows:
            return {}
        dates: dict = {}
        for invoice_id, payment_date in (
            session.query(fk_column, Payment.payment_date)
            .join(Payment, Payment.id == PaymentAllocation.payment_id)
            .filter(fk_column.in_([r.id for r in rows]))
            .order_by(PaymentAllocation.created_at.asc())
            .all()
        ):
            dates[invoice_id] = payment_date
        return dates

    def _avg_days(rows, fk_column):
        if not rows:
            return 0
        payment_dates = _payment_dates(rows, fk_column)
        today = date.today()
        total_days = sum(((payment_dates.get(r.id) or today) - r.invoice_date).days for r in rows)
        return round(total_days / len(rows))

    dso = _avg_days(ar_rows, PaymentAllocation.ar_invoice_id)
    dpo = _avg_days(ap_rows, PaymentAllocation.ap_invoice_id)

    return {"daysSalesOutstanding": dso, "daysPayablesOutstanding": dpo, "note": "Days inventory outstanding requires cost-of-sales, which is out of scope."}
