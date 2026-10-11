"""GRN "Invoice number" field - compulsory on receipt, unique per (tenant,
vendor) - see grns.py's GrnBody.invoiceNumber and the duplicate check in
_create_grn()."""

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from tests.flaskcompat import db as _db


@pytest.fixture
def two_vendor_pos(app, default_tenant_id):
    """Two POs for vendor A (so a duplicate invoice number within the same
    vendor can be tested without over-receiving a single PO line) and one PO
    for vendor B (so cross-vendor reuse of the same invoice number can be
    tested), all issued and receivable, same warehouse/product."""
    from app.models.location import Location
    from app.models.party import Party
    from app.models.po_line import PoLine
    from app.models.product import Product
    from app.models.purchase_order import PurchaseOrder
    from app.models.warehouse import Warehouse

    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        product = Product(tenant_id=default_tenant_id, sku=f"TST-INV-{suffix}", name="Invoice Number Test RM", type="raw_material", uom="KG", status="active")
        vendor_a = Party(tenant_id=default_tenant_id, code=f"VENA-{suffix}", legal_name="Vendor A", display_name="Vendor A", type="vendor", status="active")
        vendor_b = Party(tenant_id=default_tenant_id, code=f"VENB-{suffix}", legal_name="Vendor B", display_name="Vendor B", type="vendor", status="active")
        warehouse = Warehouse(tenant_id=default_tenant_id, code=f"WH-INV-{suffix}", name="Invoice Number Test Warehouse", status="active")
        _db.session.add_all([product, vendor_a, vendor_b, warehouse])
        _db.session.flush()

        quarantine = Location(tenant_id=default_tenant_id, warehouse_id=warehouse.id, code=f"QTN-{suffix}", type="quarantine", status="active")
        _db.session.add(quarantine)
        _db.session.flush()

        pos = {}
        for key, vendor in (("a1", vendor_a), ("a2", vendor_a), ("b1", vendor_b)):
            po = PurchaseOrder(
                tenant_id=default_tenant_id, number=f"PO-INV-{key}-{suffix}", vendor_id=vendor.id, vendor_name=vendor.display_name,
                warehouse_id=warehouse.id, warehouse_code=warehouse.code, status="issued", expected_date=date.today() + timedelta(days=1),
            )
            _db.session.add(po)
            _db.session.flush()
            line = PoLine(tenant_id=default_tenant_id, po_id=po.id, line_no=1, product_id=product.id, sku=product.sku, quantity=Decimal("10"), uom=product.uom, unit_price=Decimal("50"), tax_code="NA")
            _db.session.add(line)
            _db.session.flush()
            pos[key] = {"po_id": po.id, "line_id": line.id}
        _db.session.commit()

        yield {"warehouse_id": warehouse.id, "pos": pos}

        from app.models.grn import Grn
        from app.models.grn_line import GrnLine
        from app.models.inventory_item import InventoryItem

        po_ids = [p["po_id"] for p in pos.values()]
        grn_ids = [g.id for g in Grn.query.filter(Grn.po_id.in_(po_ids)).all()]
        InventoryItem.query.filter(InventoryItem.grn_id.in_(grn_ids)).delete(synchronize_session=False)
        GrnLine.query.filter(GrnLine.grn_id.in_(grn_ids)).delete(synchronize_session=False)
        Grn.query.filter(Grn.id.in_(grn_ids)).delete(synchronize_session=False)
        PoLine.query.filter(PoLine.po_id.in_(po_ids)).delete(synchronize_session=False)
        PurchaseOrder.query.filter(PurchaseOrder.id.in_(po_ids)).delete(synchronize_session=False)
        Location.query.filter_by(id=quarantine.id).delete(synchronize_session=False)
        Product.query.filter_by(id=product.id).delete(synchronize_session=False)
        Party.query.filter(Party.id.in_([vendor_a.id, vendor_b.id])).delete(synchronize_session=False)
        Warehouse.query.filter_by(id=warehouse.id).delete(synchronize_session=False)
        _db.session.commit()


@pytest.fixture
def admin_access(client, fresh_admin):
    resp = client.post("/api/v1/auth/login", json={"email": fresh_admin["email"], "password": fresh_admin["password"]})
    return resp.get_json()["accessToken"]


def _receive(client, headers, two_vendor_pos, po_key, invoice_number):
    po = two_vendor_pos["pos"][po_key]
    return client.post(
        "/api/v1/grns",
        json={
            "poId": str(po["po_id"]),
            "warehouseId": str(two_vendor_pos["warehouse_id"]),
            "invoiceNumber": invoice_number,
            "lines": [{"poLineId": str(po["line_id"]), "receivedQty": "5"}],
        },
        headers=headers,
    )


def test_invoice_number_is_compulsory(client, admin_access, two_vendor_pos):
    po = two_vendor_pos["pos"]["a1"]
    resp = client.post(
        "/api/v1/grns",
        json={
            "poId": str(po["po_id"]),
            "warehouseId": str(two_vendor_pos["warehouse_id"]),
            "lines": [{"poLineId": str(po["line_id"]), "receivedQty": "5"}],
        },
        headers={"Authorization": f"Bearer {admin_access}"},
    )
    assert resp.status_code == 400, resp.get_json()
    assert resp.get_json()["errors"][0]["field"] == "invoiceNumber"


def test_duplicate_invoice_number_for_same_vendor_is_rejected(client, admin_access, two_vendor_pos):
    headers = {"Authorization": f"Bearer {admin_access}"}
    invoice_number = f"INV-{uuid.uuid4().hex[:8].upper()}"

    first = _receive(client, headers, two_vendor_pos, "a1", invoice_number)
    assert first.status_code == 201, first.get_json()

    dupe = _receive(client, headers, two_vendor_pos, "a2", invoice_number)
    assert dupe.status_code == 409, dupe.get_json()
    assert dupe.get_json()["code"] == "DUPLICATE_GRN_INVOICE_NUMBER"


def test_same_invoice_number_for_different_vendor_is_allowed(client, admin_access, two_vendor_pos):
    headers = {"Authorization": f"Bearer {admin_access}"}
    invoice_number = f"INV-{uuid.uuid4().hex[:8].upper()}"

    vendor_a = _receive(client, headers, two_vendor_pos, "a1", invoice_number)
    assert vendor_a.status_code == 201, vendor_a.get_json()

    vendor_b = _receive(client, headers, two_vendor_pos, "b1", invoice_number)
    assert vendor_b.status_code == 201, vendor_b.get_json()
