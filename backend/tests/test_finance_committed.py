"""New coverage - GET /api/v1/finance/committed, backing the Finance module's
"Committed AR/AP" tab: future payables (issued POs not yet GRN'd) and future
receivables (confirmed orders not yet allocated) - value that hasn't reached
a real ApInvoice/ArInvoice row yet, so it can't be read off the existing
aging report."""

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from tests.flaskcompat import db as _db


@pytest.fixture
def admin_access(client, fresh_admin):
    resp = client.post("/api/v1/auth/login", json={"email": fresh_admin["email"], "password": fresh_admin["password"]})
    return resp.get_json()["accessToken"]


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def committed_fixtures(app, default_tenant_id):
    from app.models.order import Order
    from app.models.order_line import OrderLine
    from app.models.party import Party
    from app.models.po_line import PoLine
    from app.models.product import Product
    from app.models.purchase_order import PurchaseOrder
    from app.models.warehouse import Warehouse

    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        vendor = Party(tenant_id=default_tenant_id, code=f"VEN-CMT-{suffix}", legal_name="Committed Test Vendor", display_name="Committed Test Vendor", type="vendor", status="active")
        customer = Party(tenant_id=default_tenant_id, code=f"CUST-CMT-{suffix}", legal_name="Committed Test Customer", display_name="Committed Test Customer", type="customer", status="active")
        warehouse = Warehouse(tenant_id=default_tenant_id, code=f"WH-CMT-{suffix}", name="Committed Test Warehouse", status="active")
        rm = Product(tenant_id=default_tenant_id, sku=f"TST-CMTRM-{suffix}", name="Committed Test RM", type="raw_material", uom="KG", status="active")
        fg = Product(tenant_id=default_tenant_id, sku=f"TST-CMTFG-{suffix}", name="Committed Test FG", type="finished_good", uom="UNIT", status="active")
        _db.session.add_all([vendor, customer, warehouse, rm, fg])
        _db.session.flush()

        # Issued PO: 100 units ordered, 40 already received -> 60 still open at ₹10/unit = ₹600 committed.
        po = PurchaseOrder(
            tenant_id=default_tenant_id, number=f"PO-CMT-{suffix}", vendor_id=vendor.id, vendor_name=vendor.display_name,
            warehouse_id=warehouse.id, warehouse_code=warehouse.code, status="issued", expected_date=date.today() + timedelta(days=7),
        )
        _db.session.add(po)
        _db.session.flush()
        po_line = PoLine(tenant_id=default_tenant_id, po_id=po.id, line_no=1, product_id=rm.id, sku=rm.sku, quantity="100", uom="KG", unit_price="10", tax_code="NA", received_qty="40", rejected_qty="0", status="partial")
        _db.session.add(po_line)

        # A draft PO (not issued) - must NOT count as committed.
        draft_po = PurchaseOrder(
            tenant_id=default_tenant_id, number=f"PO-CMTD-{suffix}", vendor_id=vendor.id, vendor_name=vendor.display_name,
            warehouse_id=warehouse.id, warehouse_code=warehouse.code, status="draft", expected_date=date.today() + timedelta(days=7),
        )
        _db.session.add(draft_po)
        _db.session.flush()
        draft_line = PoLine(tenant_id=default_tenant_id, po_id=draft_po.id, line_no=1, product_id=rm.id, sku=rm.sku, quantity="50", uom="KG", unit_price="10", tax_code="NA")
        _db.session.add(draft_line)

        # Confirmed order: 20 units ordered, 5 already allocated -> 15 open at ₹100/unit = ₹1500 committed.
        order = Order(
            tenant_id=default_tenant_id, number=f"SO-CMT-{suffix}", customer_id=customer.id, customer_name=customer.display_name,
            status="confirmed", promised_date=date.today() + timedelta(days=7), subtotal="2000", tax_total="0", total="2000",
        )
        _db.session.add(order)
        _db.session.flush()
        order_line = OrderLine(tenant_id=default_tenant_id, order_id=order.id, line_no=1, product_id=fg.id, sku=fg.sku, quantity="20", uom="UNIT", unit_price="100", tax_code="NA", allocated_qty="5", net_amount="2000", gross_amount="2000", status="open")
        _db.session.add(order_line)

        # A fully-allocated order - must NOT count as committed (no open qty left).
        allocated_order = Order(
            tenant_id=default_tenant_id, number=f"SO-CMTA-{suffix}", customer_id=customer.id, customer_name=customer.display_name,
            status="allocated", promised_date=date.today() + timedelta(days=7), subtotal="500", tax_total="0", total="500",
        )
        _db.session.add(allocated_order)
        _db.session.flush()
        allocated_line = OrderLine(tenant_id=default_tenant_id, order_id=allocated_order.id, line_no=1, product_id=fg.id, sku=fg.sku, quantity="5", uom="UNIT", unit_price="100", tax_code="NA", allocated_qty="5", net_amount="500", gross_amount="500", status="allocated")
        _db.session.add(allocated_line)

        _db.session.commit()
        ids = {
            "tenant_id": default_tenant_id, "po_id": po.id, "draft_po_id": draft_po.id, "order_id": order.id, "allocated_order_id": allocated_order.id,
            "vendor_id": vendor.id, "customer_id": customer.id, "warehouse_id": warehouse.id, "rm_id": rm.id, "fg_id": fg.id,
        }
        yield ids

        PoLine.query.filter(PoLine.po_id.in_([po.id, draft_po.id])).delete(synchronize_session=False)
        PurchaseOrder.query.filter(PurchaseOrder.id.in_([po.id, draft_po.id])).delete(synchronize_session=False)
        OrderLine.query.filter(OrderLine.order_id.in_([order.id, allocated_order.id])).delete(synchronize_session=False)
        Order.query.filter(Order.id.in_([order.id, allocated_order.id])).delete(synchronize_session=False)
        Party.query.filter(Party.id.in_([vendor.id, customer.id])).delete(synchronize_session=False)
        Product.query.filter(Product.id.in_([rm.id, fg.id])).delete(synchronize_session=False)
        Warehouse.query.filter_by(id=warehouse.id).delete(synchronize_session=False)
        _db.session.commit()


def test_committed_ap_reflects_only_the_open_unreceived_quantity(client, admin_access, committed_fixtures):
    resp = client.get("/api/v1/finance/committed", headers=_headers(admin_access))
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()

    po_doc = next(d for d in body["ap"]["documents"] if d["number"].startswith("PO-CMT-"))
    assert Decimal(po_doc["committed"]) == Decimal("600.000000")  # (100-40) * 10
    assert not any(d["number"].startswith("PO-CMTD-") for d in body["ap"]["documents"])  # draft PO excluded


def test_committed_ar_reflects_only_the_open_unallocated_quantity(client, admin_access, committed_fixtures):
    resp = client.get("/api/v1/finance/committed", headers=_headers(admin_access))
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()

    order_doc = next(d for d in body["ar"]["documents"] if d["number"].startswith("SO-CMT-"))
    assert Decimal(order_doc["committed"]) == Decimal("1500.000000")  # (20-5) * 100
    assert not any(d["number"].startswith("SO-CMTA-") for d in body["ar"]["documents"])  # fully-allocated order excluded


def test_committed_totals_match_the_sum_of_documents(client, admin_access, committed_fixtures):
    resp = client.get("/api/v1/finance/committed", headers=_headers(admin_access))
    body = resp.get_json()
    ap_sum = sum(Decimal(d["committed"]) for d in body["ap"]["documents"])
    ar_sum = sum(Decimal(d["committed"]) for d in body["ar"]["documents"])
    assert Decimal(body["ap"]["total"]) == ap_sum
    assert Decimal(body["ar"]["total"]) == ar_sum
    assert body["asOf"] == date.today().isoformat()
