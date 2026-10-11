"""New coverage - POST /orders/<id>/invoice (generate) and GET /orders/<id>/
invoice/download (re-download) - the pair backing the new Finance > Invoices
tab. Builds a shipped order directly (Order/OrderLine/Reservation rows) so
the fixture doesn't need to walk through BOM/production/allocation just to
reach the one status invoicing actually cares about."""

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from tests.flaskcompat import db as _db


@pytest.fixture
def shipped_order(app, default_tenant_id):
    from app.models.business_entity import BusinessEntity
    from app.models.order import Order
    from app.models.order_line import OrderLine
    from app.models.party import Party
    from app.models.party_address import PartyAddress
    from app.models.product import Product
    from app.models.reservation import Reservation
    from app.models.warehouse import Warehouse

    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        fg = Product(tenant_id=default_tenant_id, sku=f"TST-INV-{suffix}", name="Invoice Test Widget", type="finished_good", uom="UNIT", status="active", hsn_code="8507")
        warehouse = Warehouse(tenant_id=default_tenant_id, code=f"WH-INV-{suffix}", name="Invoice Test Warehouse", status="active", state_code="29")
        seller = BusinessEntity(
            tenant_id=default_tenant_id, code=f"ENT-INV-{suffix}", name="Simple Battery Science Pvt Ltd", status="active",
            tax_id="29AAFCF7382N1ZU", tax_id_country="IN", pan="AAFCF7382N",
            bank_name="IDFC First Bank", bank_branch="Koramangala Branch", bank_account_number="10196183256", bank_ifsc="IDFB0080152",
        )
        customer = Party(
            tenant_id=default_tenant_id, code=f"CUST-INV-{suffix}", legal_name="DR Traders", display_name="DR Traders", type="customer", status="active",
            tax_id="09AWJPV5553A1ZA", tax_id_country="IN",
        )
        _db.session.add_all([fg, warehouse, seller, customer])
        _db.session.flush()

        billing = PartyAddress(tenant_id=default_tenant_id, party_id=customer.id, type="billing", line1="5, Saray Road", city="Etah", state_code="09", postal_code="207247", is_default=True)
        _db.session.add(billing)

        order = Order(
            tenant_id=default_tenant_id, number=f"SO-INV-{suffix}", customer_id=customer.id, customer_name=customer.display_name, customer_ref="CUST-PO-77",
            status="shipped", promised_date=date.today() + timedelta(days=7),
            subtotal="62000", tax_total="11160", total="73160", payment_terms="Net 30 days",
        )
        _db.session.add(order)
        _db.session.flush()

        line = OrderLine(
            tenant_id=default_tenant_id, order_id=order.id, line_no=1, product_id=fg.id, sku=fg.sku, description="51.2VX100Ah Repurposed Cells, Floor Mount",
            quantity="2", uom="UNIT", unit_price="31000", tax_code="GST18", tax_rate="18", net_amount="62000", tax_amount="11160", gross_amount="73160", status="shipped",
        )
        _db.session.add(line)
        _db.session.flush()

        reservation = Reservation(tenant_id=default_tenant_id, product_id=fg.id, sku=fg.sku, warehouse_id=warehouse.id, quantity="2", uom="UNIT", status="issued", order_id=order.id, order_line_id=line.id)
        _db.session.add(reservation)
        _db.session.flush()
        line.reservation_id = reservation.id
        _db.session.commit()

        ids = {"tenant_id": default_tenant_id, "order_id": order.id, "order_number": order.number, "seller_id": seller.id, "line_id": line.id}
        yield ids

        from app.models.ar_invoice import ArInvoice
        from app.models.document import Document
        from app.models.invoice import Invoice
        from app.models.invoice_line import InvoiceLine

        invoice_ids = [i.id for i in Invoice.query.filter_by(order_id=order.id).all()]
        ArInvoice.query.filter_by(order_id=order.id).delete(synchronize_session=False)
        if invoice_ids:
            InvoiceLine.query.filter(InvoiceLine.invoice_id.in_(invoice_ids)).delete(synchronize_session=False)
            Document.query.filter_by(tenant_id=default_tenant_id, related_type="invoice").filter(Document.related_id.in_([str(i) for i in invoice_ids])).delete(synchronize_session=False)
            Invoice.query.filter(Invoice.id.in_(invoice_ids)).delete(synchronize_session=False)
        Reservation.query.filter_by(id=reservation.id).delete(synchronize_session=False)
        OrderLine.query.filter_by(order_id=order.id).delete(synchronize_session=False)
        Order.query.filter_by(id=order.id).delete(synchronize_session=False)
        PartyAddress.query.filter_by(party_id=customer.id).delete(synchronize_session=False)
        Party.query.filter_by(id=customer.id).delete(synchronize_session=False)
        BusinessEntity.query.filter_by(id=seller.id).delete(synchronize_session=False)
        Product.query.filter_by(id=fg.id).delete(synchronize_session=False)
        Warehouse.query.filter_by(id=warehouse.id).delete(synchronize_session=False)
        _db.session.commit()


def _build_order(tenant_id, *, status: str):
    """Constructs a minimal standalone order (with its own customer Party,
    required by the FK) at the given status, for tests that need a starting
    status other than "shipped" - built fresh rather than mutating an
    already-committed order's status via a nested app-context, which left
    the object invoice_order() reads looking stale (SQLAlchemy identity-map
    staleness across the fixture's still-open outer app-context - this is
    what the earlier version of this test hit). Must be called inside an
    open app context; returns (order_id, customer_id)."""
    from app.models.order import Order
    from app.models.party import Party

    suffix = uuid.uuid4().hex[:8]
    customer = Party(tenant_id=tenant_id, code=f"CUST-INVB-{suffix}", legal_name="Standalone Test Customer", display_name="Standalone Test Customer", type="customer", status="active")
    _db.session.add(customer)
    _db.session.flush()
    order = Order(
        tenant_id=tenant_id, number=f"SO-INVB-{suffix}", customer_id=customer.id, customer_name=customer.display_name,
        status=status, promised_date=date.today() + timedelta(days=7), subtotal="100", tax_total="0", total="100",
    )
    _db.session.add(order)
    _db.session.commit()
    return order.id, customer.id


def _cleanup_order(order_id, customer_id):
    from app.models.ar_invoice import ArInvoice
    from app.models.document import Document
    from app.models.invoice import Invoice
    from app.models.invoice_line import InvoiceLine
    from app.models.order import Order
    from app.models.party import Party

    invoice_ids = [i.id for i in Invoice.query.filter_by(order_id=order_id).all()]
    ArInvoice.query.filter_by(order_id=order_id).delete(synchronize_session=False)
    if invoice_ids:
        InvoiceLine.query.filter(InvoiceLine.invoice_id.in_(invoice_ids)).delete(synchronize_session=False)
        Document.query.filter_by(related_type="invoice").filter(Document.related_id.in_([str(i) for i in invoice_ids])).delete(synchronize_session=False)
        Invoice.query.filter(Invoice.id.in_(invoice_ids)).delete(synchronize_session=False)
    Order.query.filter_by(id=order_id).delete(synchronize_session=False)
    Party.query.filter_by(id=customer_id).delete(synchronize_session=False)
    _db.session.commit()


@pytest.fixture
def admin_access(client, fresh_admin):
    resp = client.post("/api/v1/auth/login", json={"email": fresh_admin["email"], "password": fresh_admin["password"]})
    return resp.get_json()["accessToken"]


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_generate_invoice_leaves_order_status_untouched_and_sets_document_id(app, client, admin_access, shipped_order):
    """Invoicing is decoupled from order status entirely (order_state.py's
    module docstring) - generating an invoice no longer stamps status as
    "invoiced"; the order stays wherever it already was, and invoiceId is
    the sole "has been invoiced" signal."""
    resp = client.post(
        f"/api/v1/orders/{shipped_order['order_id']}/invoice",
        json={"businessEntityId": str(shipped_order["seller_id"])},
        headers=_headers(admin_access),
    )
    assert resp.status_code == 201, resp.get_json()
    body = resp.get_json()
    assert body["order"]["status"] == "shipped"  # unchanged - the fixture starts it here
    assert body["order"]["invoiceId"]
    assert body["invoice"]["total"] == "73160.000000"

    with app.app_context():
        from app.models.invoice import Invoice

        invoice = Invoice.query.filter_by(order_id=shipped_order["order_id"]).one()
        assert invoice.document_id  # wired up for direct download, not left null


def test_generate_invoice_before_shipment_now_succeeds(app, client, admin_access, default_tenant_id):
    """The old "must be shipped first" rule (INVOICE_BEFORE_SHIPMENT) is
    gone - invoicing is legal at any point in an order's life, e.g. while
    still "confirmed" (not yet allocated or shipped)."""
    with app.app_context():
        order_id, customer_id = _build_order(default_tenant_id, status="confirmed")
    try:
        resp = client.post(f"/api/v1/orders/{order_id}/invoice", json={}, headers=_headers(admin_access))
        assert resp.status_code == 201, resp.get_json()
        assert resp.get_json()["order"]["status"] == "confirmed"  # untouched
        assert resp.get_json()["order"]["invoiceId"]
    finally:
        with app.app_context():
            _cleanup_order(order_id, customer_id)


def test_generate_invoice_on_a_cancelled_order_is_rejected(app, client, admin_access, default_tenant_id):
    with app.app_context():
        order_id, customer_id = _build_order(default_tenant_id, status="cancelled")
    try:
        resp = client.post(f"/api/v1/orders/{order_id}/invoice", json={}, headers=_headers(admin_access))
        assert resp.status_code == 422, resp.get_json()
        assert resp.get_json()["code"] == "ORDER_NOT_INVOICEABLE"
    finally:
        with app.app_context():
            _cleanup_order(order_id, customer_id)


def test_generate_invoice_twice_is_rejected(client, admin_access, shipped_order):
    first = client.post(f"/api/v1/orders/{shipped_order['order_id']}/invoice", json={}, headers=_headers(admin_access))
    assert first.status_code == 201, first.get_json()

    second = client.post(f"/api/v1/orders/{shipped_order['order_id']}/invoice", json={}, headers=_headers(admin_access))
    assert second.status_code >= 400  # already invoiced - the one restriction that's left
    assert second.get_json()["code"] == "ORDER_ALREADY_INVOICED"


def test_download_invoice_streams_the_pdf_repeatedly_without_regenerating(app, client, admin_access, shipped_order):
    """The actual TAX INVOICE/BILL FROM/bank-details content is asserted at
    the template layer (test_document_templates.py) against the raw HTML
    customer_invoice() builds - here the PDF engine (weasyprint/gotenberg)
    turns that into real binary PDF bytes, so this test only checks the
    plumbing: the right document comes back, with the right headers, and a
    second download re-serves the exact same file rather than regenerating."""
    generate = client.post(
        f"/api/v1/orders/{shipped_order['order_id']}/invoice",
        json={"businessEntityId": str(shipped_order["seller_id"])},
        headers=_headers(admin_access),
    )
    assert generate.status_code == 201, generate.get_json()
    invoice_number = generate.get_json()["invoice"]["number"]

    download = client.get(f"/api/v1/orders/{shipped_order['order_id']}/invoice/download", headers=_headers(admin_access))
    assert download.status_code == 200
    assert download.content_type in ("application/pdf", "text/html; charset=utf-8")  # html only if no PDF engine is configured
    assert invoice_number in download.headers["Content-Disposition"]
    assert len(download.data) > 100

    # Downloadable any number of times without re-generating.
    second_download = client.get(f"/api/v1/orders/{shipped_order['order_id']}/invoice/download", headers=_headers(admin_access))
    assert second_download.status_code == 200
    assert second_download.data == download.data

    with app.app_context():
        from app.models.invoice import Invoice

        assert Invoice.query.filter_by(order_id=shipped_order["order_id"]).count() == 1  # still just the one invoice


def test_download_invoice_before_generation_is_404(client, admin_access, shipped_order):
    resp = client.get(f"/api/v1/orders/{shipped_order['order_id']}/invoice/download", headers=_headers(admin_access))
    assert resp.status_code == 404


def test_download_invoice_with_missing_stored_file_is_a_clean_conflict_not_a_500(app, client, admin_access, shipped_order):
    """Regression test - local dev storage lives under /tmp, which doesn't
    survive a machine reboot, so a Document row can outlive its file. This
    used to raise an unhandled FileNotFoundError (500, "An unexpected error
    occurred" - see PROD-observed SO-1008/SO-1010) instead of a clean,
    explained error."""
    generate = client.post(f"/api/v1/orders/{shipped_order['order_id']}/invoice", json={}, headers=_headers(admin_access))
    assert generate.status_code == 201, generate.get_json()

    with app.app_context():
        from pathlib import Path

        from app.models.document import Document
        from app.models.invoice import Invoice
        from app.services import document_storage

        invoice = Invoice.query.filter_by(order_id=shipped_order["order_id"]).one()
        doc = Document.query.filter_by(tenant_id=shipped_order["tenant_id"], id=invoice.document_id).one()
        Path(document_storage._local_path(doc.storage_key)).unlink()  # simulate the file having gone missing

    resp = client.get(f"/api/v1/orders/{shipped_order['order_id']}/invoice/download", headers=_headers(admin_access))
    assert resp.status_code == 409
    assert resp.get_json()["code"] == "DOCUMENT_FILE_MISSING"
