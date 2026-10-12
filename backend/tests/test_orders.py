"""New test coverage for the orders domain port (no direct original-repo
equivalent file - backend_py/tests/test_order_state.py etc. cover many more
edge cases across ~9 files; this is a first end-to-end pass proving create,
tax computation, credit-limit application, audit, cancel, and the
allocate/pack/ship stock-locking path all work against a real Postgres).
Uses the same real-DB, no-mocking, explicit-cleanup philosophy as the rest
of this test suite.
"""

from __future__ import annotations

import uuid

import pytest

from app.core.db import SessionLocal


@pytest.fixture
def customer(default_tenant_id):
    from app.models.party import Party
    from app.models.party_address import PartyAddress

    party = Party(
        tenant_id=default_tenant_id,
        code=f"CUST-{uuid.uuid4().hex[:8]}",
        legal_name="Test Customer Pvt Ltd",
        display_name="Test Customer",
        type="customer",
        status="active",
        credit_limit="1000000",
        credit_used="0",
        currency="INR",
    )
    SessionLocal.add(party)
    SessionLocal.flush()
    SessionLocal.add(
        PartyAddress(
            tenant_id=default_tenant_id,
            party_id=party.id,
            type="billing",
            line1="221B Test Street",
            city="Pune",
            state_code="27",
            postal_code="411001",
            country="IN",
            is_default=True,
        )
    )
    SessionLocal.commit()
    yield party

    _delete_orders_for_customer(party.id)
    from app.models.party_address import PartyAddress as PA

    PA.query.filter_by(party_id=party.id).delete(synchronize_session=False)
    Party.query.filter_by(id=party.id).delete(synchronize_session=False)
    SessionLocal.commit()


@pytest.fixture
def product(default_tenant_id):
    from app.models.product import Product

    p = Product(
        tenant_id=default_tenant_id,
        sku=f"FG-TEST-{uuid.uuid4().hex[:8]}",
        name="Test Finished Good",
        type="finished_good",
        uom="UNIT",
        status="active",
        sellable=True,
        purchasable=False,
    )
    SessionLocal.add(p)
    SessionLocal.commit()
    yield p

    _delete_orders_for_product(p.id)
    from app.models.reservation import Reservation
    from app.models.stock_balance import StockBalance
    from app.models.stock_ledger import StockLedger

    Reservation.query.filter_by(product_id=p.id).delete(synchronize_session=False)
    StockLedger.query.filter_by(product_id=p.id).delete(synchronize_session=False)
    StockBalance.query.filter_by(product_id=p.id).delete(synchronize_session=False)
    Product.query.filter_by(id=p.id).delete(synchronize_session=False)
    SessionLocal.commit()


def _delete_orders_for_customer(customer_id) -> None:
    """Test-only cleanup helper: order_lines/orders aren't created by the
    fixtures themselves (the tests create them via the API), so both the
    `customer` and `product` fixtures need to sweep any orders left behind
    before they can delete the rows those orders reference (FK RESTRICT on
    both orders.customer_id and order_lines.product_id)."""
    from app.models.order import Order

    for order in Order.query.filter_by(customer_id=customer_id).all():
        SessionLocal.delete(order)  # cascades order_lines (ondelete="CASCADE")
    SessionLocal.flush()


def _delete_orders_for_product(product_id) -> None:
    from app.models.order import Order
    from app.models.order_line import OrderLine

    order_ids = {row.order_id for row in OrderLine.query.filter_by(product_id=product_id).all()}
    for order in Order.query.filter(Order.id.in_(order_ids)).all():
        SessionLocal.delete(order)
    SessionLocal.flush()


def _auth_headers(client, fresh_admin):
    login = client.post("/api/v1/auth/login", json={"email": fresh_admin["email"], "password": fresh_admin["password"]})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['accessToken']}"}


def test_create_order_computes_tax_and_applies_credit(client, fresh_admin, customer, product):
    headers = _auth_headers(client, fresh_admin)

    resp = client.post(
        "/api/v1/orders",
        headers=headers,
        json={
            "customerId": str(customer.id),
            "promisedDate": "2026-12-01",
            "lines": [
                {"productId": str(product.id), "quantity": "10", "uom": "UNIT", "unitPrice": "1000", "taxCode": "GST18"}
            ],
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    # 10 * 1000 = 10000 net, 18% GST = 1800 tax, total 11800.
    assert body["subtotal"] == "10000.000000"
    assert body["taxTotal"] == "1800.000000"
    assert body["total"] == "11800.000000"
    assert body["status"] == "confirmed"
    assert len(body["lines"]) == 1
    assert body["lines"][0]["sku"] == product.sku

    # Credit usage was applied at creation (no draft stage).
    SessionLocal.expire_all()
    from app.models.party import Party

    refreshed = Party.query.filter_by(id=customer.id).first()
    assert str(refreshed.credit_used) == "11800.000000"


def test_create_order_rejects_client_supplied_total_mismatch(client, fresh_admin, customer, product):
    headers = _auth_headers(client, fresh_admin)
    resp = client.post(
        "/api/v1/orders",
        headers=headers,
        json={
            "customerId": str(customer.id),
            "promisedDate": "2026-12-01",
            "lines": [{"productId": str(product.id), "quantity": "1", "uom": "UNIT", "unitPrice": "100", "taxCode": "GST18"}],
            "expectedTotal": "999999",
        },
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "TOTAL_MISMATCH"


def test_create_order_unknown_tax_code_rejected(client, fresh_admin, customer, product):
    headers = _auth_headers(client, fresh_admin)
    resp = client.post(
        "/api/v1/orders",
        headers=headers,
        json={
            "customerId": str(customer.id),
            "promisedDate": "2026-12-01",
            "lines": [{"productId": str(product.id), "quantity": "1", "uom": "UNIT", "unitPrice": "100", "taxCode": "NOT_A_CODE"}],
        },
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "ORDER_VALIDATION_FAILED"


def test_cancel_order_releases_credit(client, fresh_admin, customer, product):
    headers = _auth_headers(client, fresh_admin)
    create = client.post(
        "/api/v1/orders",
        headers=headers,
        json={
            "customerId": str(customer.id),
            "promisedDate": "2026-12-01",
            "lines": [{"productId": str(product.id), "quantity": "2", "uom": "UNIT", "unitPrice": "500", "taxCode": "GST0"}],
        },
    )
    assert create.status_code == 201
    order_id = create.json()["id"]

    cancel = client.post(f"/api/v1/orders/{order_id}/cancel", headers=headers, json={"reason": "customer changed their mind"})
    assert cancel.status_code == 200, cancel.text
    assert cancel.json()["status"] == "cancelled"

    SessionLocal.expire_all()
    from app.models.party import Party

    refreshed = Party.query.filter_by(id=customer.id).first()
    assert str(refreshed.credit_used) == "0.000000"


def test_order_requires_permission(client, customer, product):
    resp = client.post(
        "/api/v1/orders",
        json={"customerId": str(customer.id), "promisedDate": "2026-12-01", "lines": [{"productId": str(product.id), "quantity": "1", "uom": "UNIT", "unitPrice": "1", "taxCode": "GST0"}]},
    )
    assert resp.status_code == 401


def test_allocate_pack_ship_order_moves_stock(client, fresh_admin, customer, product, default_tenant_id):
    """End-to-end: seed a warehouse + available stock directly (no
    warehouse/inventory domain routes ported yet), create an order, allocate
    via FEFO/FIFO, pack, then ship - and verify the ledger actually moved
    stock out of `available`."""
    from app.models.factory import Factory
    from app.models.warehouse import Warehouse
    from app.services import inventory_ledger
    from app.services.inventory_ledger import LedgerPosting

    factory = Factory(tenant_id=default_tenant_id, code=f"FAC-{uuid.uuid4().hex[:6]}", name="Test Factory", status="active")
    SessionLocal.add(factory)
    SessionLocal.flush()
    warehouse = Warehouse(tenant_id=default_tenant_id, factory_id=factory.id, code=f"WH-{uuid.uuid4().hex[:6]}", name="Test Warehouse", state_code="27", status="active")
    SessionLocal.add(warehouse)
    SessionLocal.commit()

    # Receive 50 units into `available` directly via the ledger (bypassing
    # GRN posting, which isn't ported yet).
    inventory_ledger.post(
        LedgerPosting(
            tenant_id=default_tenant_id,
            product_id=product.id,
            sku=product.sku,
            warehouse_id=warehouse.id,
            quantity="50",
            uom="UNIT",
            bucket="available",
            movement_type="receipt",
            reference_type="test-seed",
            reference_id=str(uuid.uuid4()),
        )
    )
    SessionLocal.commit()

    headers = _auth_headers(client, fresh_admin)
    create = client.post(
        "/api/v1/orders",
        headers=headers,
        json={
            "customerId": str(customer.id),
            "promisedDate": "2026-12-01",
            "lines": [{"productId": str(product.id), "quantity": "5", "uom": "UNIT", "unitPrice": "200", "taxCode": "GST0"}],
        },
    )
    assert create.status_code == 201, create.text
    order = create.json()
    order_id = order["id"]
    line_id = order["lines"][0]["id"]

    allocate = client.post(f"/api/v1/orders/{order_id}/allocate", headers=headers, json={"warehouseId": str(warehouse.id)})
    assert allocate.status_code == 200, allocate.text
    assert allocate.json()["status"] == "allocated"

    pack = client.post(f"/api/v1/orders/lines/{line_id}/pack", headers=headers, json={"quantity": "5"})
    assert pack.status_code == 200, pack.text
    assert pack.json()["packingStatus"] == "packed"

    order_pack = client.post(f"/api/v1/orders/{order_id}/pack", headers=headers)
    assert order_pack.status_code == 200, order_pack.text

    ship = client.post(f"/api/v1/orders/{order_id}/ship", headers=headers)
    assert ship.status_code == 200, ship.text
    assert ship.json()["status"] == "shipped"
    assert ship.json()["lines"][0]["shippedQty"] == "5.000000"

    buckets = inventory_ledger.bucket_totals(default_tenant_id, product.id, warehouse.id)
    assert buckets["available"] == "45.000000"
    assert buckets["reserved"] == "0.000000"


def _cleanup_order_to_cash(order_id: str, customer_id) -> None:
    """Sweeps the invoice/AR/payment/logistics/document rows the
    order-to-cash test creates - all of them hang off the order or the
    customer, so they must go before the fixtures delete either."""
    from app.models.ar_invoice import ArInvoice
    from app.models.document import Document
    from app.models.invoice import Invoice
    from app.models.invoice_line import InvoiceLine
    from app.models.order import Order
    from app.models.payment import Payment
    from app.models.payment_allocation import PaymentAllocation
    from app.models.transport_request import TransportRequest

    oid = uuid.UUID(order_id)
    invoice_ids = [i.id for i in Invoice.query.filter_by(order_id=oid).all()]
    Order.query.filter_by(id=oid).update({"invoice_id": None, "logistics_request_id": None}, synchronize_session=False)
    payment_ids = [p.id for p in Payment.query.filter_by(party_id=customer_id).all()]
    if payment_ids:
        PaymentAllocation.query.filter(PaymentAllocation.payment_id.in_(payment_ids)).delete(synchronize_session=False)
        Payment.query.filter(Payment.id.in_(payment_ids)).delete(synchronize_session=False)
    ArInvoice.query.filter_by(order_id=oid).delete(synchronize_session=False)
    TransportRequest.query.filter_by(order_id=oid).delete(synchronize_session=False)
    if invoice_ids:
        Document.query.filter(Document.related_type == "invoice", Document.related_id.in_([str(i) for i in invoice_ids])).delete(synchronize_session=False)
        InvoiceLine.query.filter(InvoiceLine.invoice_id.in_(invoice_ids)).delete(synchronize_session=False)
        Invoice.query.filter(Invoice.id.in_(invoice_ids)).delete(synchronize_session=False)
    SessionLocal.commit()


def test_order_to_cash_invoice_ar_payment_and_auto_logistics(client, fresh_admin, customer, product, default_tenant_id):
    """The full order-to-cash loop now that finance/documents/logistics are
    ported: allocate -> pack -> ship -> invoice (intra-state GST split, PDF
    document, AR receivable posted in the same transaction) -> download ->
    fulfil, then a customer receipt that settles the AR invoice, mirrors
    payment back onto the order and auto-raises the transport request."""
    from app.models.factory import Factory
    from app.models.warehouse import Warehouse
    from app.services import inventory_ledger
    from app.services.inventory_ledger import LedgerPosting

    headers = _auth_headers(client, fresh_admin)
    factory = Factory(tenant_id=default_tenant_id, code=f"FAC-{uuid.uuid4().hex[:6]}", name="O2C Factory", status="active")
    SessionLocal.add(factory)
    SessionLocal.flush()
    warehouse = Warehouse(tenant_id=default_tenant_id, factory_id=factory.id, code=f"WH-{uuid.uuid4().hex[:6]}", name="O2C Warehouse", state_code="27", status="active")
    SessionLocal.add(warehouse)
    SessionLocal.commit()
    inventory_ledger.post(
        LedgerPosting(tenant_id=default_tenant_id, product_id=product.id, sku=product.sku, warehouse_id=warehouse.id, quantity="10", uom="UNIT", bucket="available", movement_type="receipt", reference_type="test-seed", reference_id=str(uuid.uuid4()))
    )
    SessionLocal.commit()

    order = client.post(
        "/api/v1/orders",
        headers=headers,
        json={"customerId": str(customer.id), "promisedDate": "2026-12-01", "lines": [{"productId": str(product.id), "quantity": "2", "uom": "UNIT", "unitPrice": "1000", "taxCode": "GST18"}]},
    ).json()
    order_id, line_id = order["id"], order["lines"][0]["id"]

    assert client.post(f"/api/v1/orders/{order_id}/allocate", headers=headers, json={"warehouseId": str(warehouse.id)}).status_code == 200
    assert client.post(f"/api/v1/orders/lines/{line_id}/pack", headers=headers, json={"quantity": "2"}).status_code == 200
    assert client.post(f"/api/v1/orders/{order_id}/pack", headers=headers).status_code == 200
    assert client.post(f"/api/v1/orders/{order_id}/ship", headers=headers).status_code == 200

    invoice = client.post(f"/api/v1/orders/{order_id}/invoice", headers=headers, json={})
    assert invoice.status_code == 201, invoice.text
    inv = invoice.json()["invoice"]
    assert inv["total"] == "2360.000000"  # 2000 net + 18% GST

    listed = client.get("/api/v1/invoices", headers=headers, params={"q": inv["number"]}).json()["data"]
    assert len(listed) == 1
    # Warehouse state (27) == customer billing state (27) -> CGST + SGST, no IGST.
    assert listed[0]["cgst"] == "180.000000" and listed[0]["sgst"] == "180.000000" and listed[0]["igst"] == "0.000000"
    assert listed[0]["orderNumber"] == order["number"]

    again = client.post(f"/api/v1/orders/{order_id}/invoice", headers=headers, json={})
    assert again.status_code == 422 and again.json()["code"] == "ORDER_ALREADY_INVOICED"

    download = client.get(f"/api/v1/orders/{order_id}/invoice/download", headers=headers)
    assert download.status_code == 200 and inv["number"].encode() in download.content

    # Finance got the receivable in the same transaction.
    ar = client.get("/api/v1/ar", headers=headers, params={"customerId": str(customer.id)}).json()["data"]
    assert len(ar) == 1 and ar[0]["amount"] == "2360.000000" and ar[0]["status"] == "open"
    ar_id = ar[0]["id"]

    # A customer receipt for the full amount settles it and closes the loop.
    pay = client.post("/api/v1/ar/payments", headers=headers, json={"partyId": str(customer.id), "amount": "2360", "allocations": [{"invoiceId": ar_id, "amount": "2360"}]})
    assert pay.status_code == 201, pay.text
    assert len(pay.json()["settledInvoices"]) == 1

    after = client.get(f"/api/v1/orders/{order_id}", headers=headers).json()
    assert after["fullyPaid"] is True and after["paidAmount"] == "2360.000000"
    assert after["logisticsState"] == "auto_raised" and after["logisticsRequestId"]
    requests_for_order = client.get("/api/v1/transport-requests", headers=headers, params={"orderId": order_id}).json()["data"]
    assert len(requests_for_order) == 1

    fulfil = client.post(f"/api/v1/orders/{order_id}/fulfill", headers=headers, json={})
    assert fulfil.status_code == 200 and fulfil.json()["status"] == "fulfilled"

    SessionLocal.expire_all()
    from app.models.party import Party

    assert str(Party.query.filter_by(id=customer.id).first().credit_used) == "0.000000"  # released on settlement

    _cleanup_order_to_cash(order_id, customer.id)


def test_list_orders_with_include_lines(client, fresh_admin, customer, product):
    headers = _auth_headers(client, fresh_admin)
    order_res = client.post(
        "/api/v1/orders",
        headers=headers,
        json={
            "customerId": str(customer.id),
            "promisedDate": "2026-12-01",
            "lines": [{"productId": str(product.id), "quantity": "3", "uom": "UNIT", "unitPrice": "50", "taxCode": "GST0"}],
        },
    )
    assert order_res.status_code == 201, order_res.text
    order_id = order_res.json()["id"]

    # Without includeLines: lines key omitted
    resp_no_lines = client.get("/api/v1/orders", headers=headers, params={"customerId": str(customer.id)})
    assert resp_no_lines.status_code == 200
    item = next(o for o in resp_no_lines.json()["data"] if o["id"] == order_id)
    assert "lines" not in item

    # With includeLines=true: lines batch-loaded
    resp_lines = client.get("/api/v1/orders", headers=headers, params={"customerId": str(customer.id), "includeLines": "true"})
    assert resp_lines.status_code == 200
    item_with_lines = next(o for o in resp_lines.json()["data"] if o["id"] == order_id)
    assert "lines" in item_with_lines
    assert len(item_with_lines["lines"]) == 1
    assert item_with_lines["lines"][0]["productId"] == str(product.id)

    _cleanup_order_to_cash(order_id, customer.id)
