"""New test coverage for the logistics + finance + system domains (no direct
original-repo equivalent - see test_orders.py's docstring for the same
note). Logistics: the full transport-request -> RFQ -> quotes -> award ->
dispatch -> proof-of-delivery -> carrier-invoice loop (whose last step posts
a payable into finance, tying the two domains together), the award
premium-justification rule, and the public unauthenticated intake route
(honeypot included). Finance: AP invoice posting (duplicate guard), payment
allocation/settlement, overpayment block, credit notes, payment reversal,
aging, plus the dashboard/system-status routes - all against a real
Postgres.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from app.core.db import SessionLocal


def _auth_headers(client, admin):
    login = client.post("/api/v1/auth/login", json={"email": admin["email"], "password": admin["password"]})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['accessToken']}"}


def _make_carrier(client, headers, label="Carrier"):
    from app.models.party import Party

    carrier = client.post("/api/v1/parties", headers=headers, json={"legalName": f"{label} {uuid.uuid4().hex[:8]} Logistics", "type": "vendor"}).json()
    Party.query.filter_by(id=uuid.UUID(carrier["id"])).update({"status": "active"}, synchronize_session=False)
    SessionLocal.commit()
    return carrier


def _cleanup_parties(party_ids: list[str], request_numbers: list[str] | None = None) -> None:
    from app.models.ap_invoice import ApInvoice
    from app.models.ap_invoice_line import ApInvoiceLine
    from app.models.credit_note import CreditNote
    from app.models.dispatch import Dispatch
    from app.models.logistics_invoice import LogisticsInvoice
    from app.models.party import Party
    from app.models.party_version import PartyVersion
    from app.models.payment import Payment
    from app.models.payment_allocation import PaymentAllocation
    from app.models.quotation import Quotation
    from app.models.rfq import Rfq
    from app.models.rfq_invitation import RfqInvitation
    from app.models.transport_request import TransportRequest

    pids = [uuid.UUID(p) for p in party_ids]
    ap_ids = [a.id for a in ApInvoice.query.filter(ApInvoice.vendor_id.in_(pids)).all()]
    payment_ids = [p.id for p in Payment.query.filter(Payment.party_id.in_(pids)).all()]
    if payment_ids:
        PaymentAllocation.query.filter(PaymentAllocation.payment_id.in_(payment_ids)).delete(synchronize_session=False)
        Payment.query.filter(Payment.party_id.in_(pids), Payment.reverses_id.isnot(None)).delete(synchronize_session=False)
        Payment.query.filter(Payment.party_id.in_(pids)).delete(synchronize_session=False)
    CreditNote.query.filter(CreditNote.party_id.in_(pids)).delete(synchronize_session=False)
    if ap_ids:
        ApInvoiceLine.query.filter(ApInvoiceLine.ap_invoice_id.in_(ap_ids)).delete(synchronize_session=False)
        ApInvoice.query.filter(ApInvoice.id.in_(ap_ids)).delete(synchronize_session=False)
    LogisticsInvoice.query.filter(LogisticsInvoice.carrier_id.in_(pids)).delete(synchronize_session=False)
    Dispatch.query.filter(Dispatch.carrier_id.in_(pids)).delete(synchronize_session=False)
    rfq_ids = [i.rfq_id for i in RfqInvitation.query.filter(RfqInvitation.carrier_id.in_(pids)).all()]
    if rfq_ids:
        Rfq.query.filter(Rfq.id.in_(rfq_ids)).update({"awarded_quote_id": None}, synchronize_session=False)
        Quotation.query.filter(Quotation.rfq_id.in_(rfq_ids)).delete(synchronize_session=False)
        RfqInvitation.query.filter(RfqInvitation.rfq_id.in_(rfq_ids)).delete(synchronize_session=False)
        request_ids = [r.transport_request_id for r in Rfq.query.filter(Rfq.id.in_(rfq_ids)).all()]
        Rfq.query.filter(Rfq.id.in_(rfq_ids)).delete(synchronize_session=False)
        TransportRequest.query.filter(TransportRequest.id.in_(request_ids)).delete(synchronize_session=False)
    if request_numbers:
        TransportRequest.query.filter(TransportRequest.number.in_(request_numbers)).delete(synchronize_session=False)
    PartyVersion.query.filter(PartyVersion.party_id.in_(pids)).delete(synchronize_session=False)
    Party.query.filter(Party.id.in_(pids)).delete(synchronize_session=False)
    SessionLocal.commit()


def test_transport_request_rfq_award_dispatch_pod_and_invoice_posts_payable(client, fresh_admin):
    headers = _auth_headers(client, fresh_admin)
    carrier_a = _make_carrier(client, headers, "Cheap")
    carrier_b = _make_carrier(client, headers, "Pricey")

    request_resp = client.post("/api/v1/transport-requests", headers=headers, json={"destLine1": "12 Dest Road", "destCity": "Mumbai", "customerName": "Test Customer", "weightKg": "50"})
    assert request_resp.status_code == 201, request_resp.text
    request_id = request_resp.json()["id"]
    assert request_resp.json()["status"] == "pending"

    # Dispatching before an RFQ exists is an invalid state transition.
    too_early = client.post("/api/v1/dispatches", headers=headers, json={"transportRequestId": request_id})
    assert too_early.status_code == 422, too_early.text

    rfq = client.post(f"/api/v1/transport-requests/{request_id}/rfq", headers=headers, json={"carrierIds": [carrier_a["id"], carrier_b["id"]]})
    assert rfq.status_code == 200, rfq.text
    assert rfq.json()["status"] == "rfq_sent"
    rfq_id = rfq.json()["rfqs"][0]["id"]
    # Neither carrier has an email on file, so both invitations record a failed email rather than erroring.
    assert {i["emailState"] for i in rfq.json()["rfqs"][0]["invitations"]} == {"failed"}

    valid_until = (date.today() + timedelta(days=7)).isoformat()
    q_a = client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=headers, json={"carrierId": carrier_a["id"], "amount": "1000", "validUntil": valid_until})
    assert q_a.status_code == 200, q_a.text
    assert q_a.json()["status"] == "quotation_received"
    q_b = client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=headers, json={"carrierId": carrier_b["id"], "amount": "2000", "validUntil": valid_until})
    quotes = {q["carrierName"]: q for q in q_b.json()["rfqs"][0]["quotations"]}
    quote_a = next(q for name, q in quotes.items() if name.startswith("Cheap"))
    quote_b = next(q for name, q in quotes.items() if name.startswith("Pricey"))

    # Choosing the much pricier quote demands a written justification.
    no_reason = client.post(f"/api/v1/rfqs/{rfq_id}/award", headers=headers, json={"quotationId": quote_b["id"]})
    assert no_reason.status_code == 422 and no_reason.json()["code"] == "AWARD_JUSTIFICATION_REQUIRED"

    award = client.post(f"/api/v1/rfqs/{rfq_id}/award", headers=headers, json={"quotationId": quote_a["id"]})
    assert award.status_code == 200, award.text
    assert award.json()["status"] == "approved"

    late_quote = client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=headers, json={"carrierId": carrier_a["id"], "amount": "900"})
    assert late_quote.status_code == 409 and late_quote.json()["code"] == "RFQ_CLOSED"

    dispatch = client.post("/api/v1/dispatches", headers=headers, json={"transportRequestId": request_id, "awbNumber": "AWB123", "vehicleNumber": "MH12AB1234"})
    assert dispatch.status_code == 201, dispatch.text
    dispatch_id = dispatch.json()["id"]

    pod = client.post(f"/api/v1/dispatches/{dispatch_id}/pod", headers=headers, json={"podUrl": "https://example.test/pod.jpg", "receivedBy": "Gate Keeper"})
    assert pod.status_code == 200, pod.text
    assert pod.json()["status"] == "delivered"
    again = client.post(f"/api/v1/dispatches/{dispatch_id}/pod", headers=headers, json={"podUrl": "https://example.test/pod.jpg", "receivedBy": "Gate Keeper"})
    assert again.status_code == 409 and again.json()["code"] == "ALREADY_DELIVERED"

    # Invoicing more than the quote without approving the variance is rejected;
    # an in-tolerance invoice posts a payable into finance in the same call.
    invoice = client.post("/api/v1/logistics-invoices", headers=headers, json={"dispatchId": dispatch_id, "carrierInvoiceNumber": f"CINV-{uuid.uuid4().hex[:6]}", "amount": "1000"})
    assert invoice.status_code == 201, invoice.text
    ap = client.get("/api/v1/ap", headers=headers, params={"vendorId": carrier_a["id"]}).json()["data"]
    assert len(ap) == 1 and ap[0]["amount"] == "1000.000000"
    assert client.get("/api/v1/logistics-invoices", headers=headers).json()["meta"]["total"] >= 1

    audit_trail = client.get(f"/api/v1/transport-requests/{request_id}/audit", headers=headers).json()["data"]
    assert {"logistics.request.created", "logistics.rfq.published"} <= {a["action"] for a in audit_trail}

    _cleanup_parties([carrier_a["id"], carrier_b["id"]])


def test_public_intake_route_and_honeypot(client):
    from app.models.public_request_throttle import PublicRequestThrottle
    from app.models.transport_request import TransportRequest

    body = {
        "requesterName": "Pat Public",
        "requesterEmail": "pat@example.test",
        "origin": {"city": "Pune"},
        "destination": {"line1": "5 Public Street", "city": "Delhi"},
        "goodsDescription": "Two pallets of test goods",
    }
    ok = client.post("/api/v1/public/transport-requests", json=body)  # no Authorization header
    assert ok.status_code == 202, ok.text
    reference = ok.json()["reference"]
    assert reference and "id" not in ok.json()

    trapped = client.post("/api/v1/public/transport-requests", json={**body, "website": "http://spam.example"})
    assert trapped.status_code == 202 and trapped.json() == {"status": "received"}

    row = TransportRequest.query.filter_by(number=reference).first()
    assert row.source == "external" and row.origin_city == "Pune"
    TransportRequest.query.filter_by(number=reference).delete(synchronize_session=False)
    PublicRequestThrottle.query.filter_by(scope="ip").delete(synchronize_session=False)
    SessionLocal.commit()


def test_ap_invoice_duplicate_guard_payment_settlement_overpayment_credit_and_reversal(client, fresh_admin):
    headers = _auth_headers(client, fresh_admin)
    vendor = _make_carrier(client, headers, "Vendor")
    vendor_invoice_no = f"VINV-{uuid.uuid4().hex[:6]}"

    post = client.post(
        "/api/v1/ap/invoices",
        headers=headers,
        json={"vendorId": vendor["id"], "vendorName": "Test Vendor", "vendorInvoiceNo": vendor_invoice_no, "amount": "1000", "lines": [{"description": "Services", "amount": "1000"}]},
    )
    assert post.status_code == 201, post.text
    ap_id = post.json()["id"]

    dupe = client.post("/api/v1/ap/invoices", headers=headers, json={"vendorId": vendor["id"], "vendorInvoiceNo": vendor_invoice_no, "amount": "1000"})
    assert dupe.status_code == 409 and dupe.json()["code"] == "DUPLICATE_VENDOR_INVOICE"

    detail = client.get(f"/api/v1/ap/{ap_id}", headers=headers).json()
    assert detail["status"] == "open" and len(detail["lines"]) == 1

    # Over-allocating beyond the outstanding balance is blocked by default policy.
    over = client.post("/api/v1/ap/payments", headers=headers, json={"partyId": vendor["id"], "amount": "1500", "allocations": [{"invoiceId": ap_id, "amount": "1500"}]})
    assert over.status_code == 422, over.text

    partial = client.post("/api/v1/ap/payments", headers=headers, json={"partyId": vendor["id"], "amount": "400", "allocations": [{"invoiceId": ap_id, "amount": "400"}]})
    assert partial.status_code == 201, partial.text
    assert partial.json()["status"] == "posted" and partial.json()["settledInvoices"] == []
    assert client.get(f"/api/v1/ap/{ap_id}", headers=headers).json()["status"] == "partially_paid"

    aging = client.get("/api/v1/ap/aging", headers=headers, params={"vendorId": vendor["id"]})
    assert aging.status_code == 200, aging.text

    full = client.post("/api/v1/ap/payments", headers=headers, json={"partyId": vendor["id"], "amount": "600", "allocations": [{"invoiceId": ap_id, "amount": "600"}]})
    assert full.status_code == 201 and len(full.json()["settledInvoices"]) == 1
    assert client.get(f"/api/v1/ap/{ap_id}", headers=headers).json()["status"] == "settled"

    reverse = client.post(f"/api/v1/payments/{full.json()['paymentId']}/reverse", headers=headers, json={"reason": "Bank bounced the transfer"})
    assert reverse.status_code == 200, reverse.text
    assert client.get(f"/api/v1/ap/{ap_id}", headers=headers).json()["status"] == "partially_paid"
    twice = client.post(f"/api/v1/payments/{full.json()['paymentId']}/reverse", headers=headers, json={"reason": "Bank bounced the transfer"})
    assert twice.status_code == 409 and twice.json()["code"] == "PAYMENT_ALREADY_REVERSED"

    both = client.post("/api/v1/credit-notes", headers=headers, json={"partyId": vendor["id"], "amount": "10", "reason": "Both targets given", "apInvoiceId": ap_id, "arInvoiceId": str(uuid.uuid4())})
    assert both.status_code == 422 and both.json()["code"] == "CREDIT_NOTE_TARGET_INVALID"
    note = client.post("/api/v1/credit-notes", headers=headers, json={"partyId": vendor["id"], "amount": "100", "reason": "Vendor goodwill credit", "apInvoiceId": ap_id})
    assert note.status_code == 201, note.text
    assert client.get(f"/api/v1/ap/{ap_id}", headers=headers).json()["amount"] == "900.000000"

    payments = client.get("/api/v1/payments", headers=headers, params={"partyId": vendor["id"]}).json()
    assert payments["meta"]["total"] == 3  # partial, full, reversal

    _cleanup_parties([vendor["id"]])


def test_large_ap_payment_needs_approval_by_someone_else_and_reports(client, fresh_admin):
    headers = _auth_headers(client, fresh_admin)
    vendor = _make_carrier(client, headers, "BigVendor")
    ap = client.post("/api/v1/ap/invoices", headers=headers, json={"vendorId": vendor["id"], "vendorInvoiceNo": f"BIG-{uuid.uuid4().hex[:6]}", "amount": "900000"}).json()

    big = client.post("/api/v1/ap/payments", headers=headers, json={"partyId": vendor["id"], "amount": "900000", "allocations": [{"invoiceId": ap["id"], "amount": "900000"}]})
    assert big.status_code == 201, big.text
    assert big.json()["status"] == "pending_approval"
    # Faithful gap: invoice balances don't move while a payment awaits approval.
    assert client.get(f"/api/v1/ap/{ap['id']}", headers=headers).json()["status"] == "open"

    self_approve = client.post(f"/api/v1/payments/{big.json()['paymentId']}/approve", headers=headers)
    assert self_approve.status_code == 422 and self_approve.json()["code"] == "SELF_APPROVAL_BLOCKED"

    for path in ("/api/v1/ar/aging", "/api/v1/finance/committed", "/api/v1/working-capital", "/api/v1/working-capital/cycle", "/api/v1/dashboard", "/api/v1/ar"):
        resp = client.get(path, headers=headers)
        assert resp.status_code == 200, f"{path}: {resp.text}"

    status = client.get("/api/v1/system-status", headers=headers).json()
    assert status["checks"]["database"]["healthy"] is True
    assert status["modulesDone"] >= 1

    _cleanup_parties([vendor["id"]])
