"""POST /inventory-items/:id/dispose - the two further terminal outcomes for
an already-rejected item, Returned to Vendor and Discarded. Only reachable
from status='rejected'; once set, there's nothing further to transition to."""

import uuid
from datetime import date

import pytest

from tests.flaskcompat import db as _db


@pytest.fixture
def rejected_item(app, default_tenant_id):
    from app.models.grn import Grn
    from app.models.grn_line import GrnLine
    from app.models.inventory_item import InventoryItem
    from app.models.party import Party
    from app.models.product import Product
    from app.models.purchase_order import PurchaseOrder
    from app.models.warehouse import Warehouse

    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        rm = Product(tenant_id=default_tenant_id, sku=f"TST-DISP-{suffix}", name="Dispose Test RM", type="raw_material", uom="KG", status="active")
        warehouse = Warehouse(tenant_id=default_tenant_id, code=f"WH-DISP-{suffix}", name="Dispose Test Warehouse", status="active")
        vendor = Party(tenant_id=default_tenant_id, code=f"VEN-DISP-{suffix}", legal_name="Dispose Test Vendor Ltd", display_name="Dispose Test Vendor", type="vendor", status="active")
        _db.session.add_all([rm, warehouse, vendor])
        _db.session.flush()

        po = PurchaseOrder(tenant_id=default_tenant_id, number=f"PO-DISP-{suffix}", vendor_id=vendor.id, vendor_name=vendor.display_name, warehouse_id=warehouse.id, warehouse_code=warehouse.code, expected_date="2027-01-01")
        _db.session.add(po)
        _db.session.flush()
        grn = Grn(tenant_id=default_tenant_id, number=f"GRN-DISP-{suffix}", po_id=po.id, warehouse_id=warehouse.id)
        _db.session.add(grn)
        _db.session.flush()
        grn_line = GrnLine(tenant_id=default_tenant_id, grn_id=grn.id, line_no=1, product_id=rm.id, sku=rm.sku, received_qty="5", accepted_qty="0", rejected_qty="5", uom="KG", unit_price="10")
        _db.session.add(grn_line)
        _db.session.flush()
        item = InventoryItem(tenant_id=default_tenant_id, inventory_id=f"INV-DISP-{suffix}", grn_id=grn.id, grn_line_id=grn_line.id, product_id=rm.id, sku=rm.sku, warehouse_id=warehouse.id, status="rejected", kind="lot", quantity="5", uom="KG", accepted_qty="0", rejected_qty="5", received_date=date.today())
        _db.session.add(item)
        _db.session.commit()

        ids = {"tenant_id": default_tenant_id, "item_id": item.id, "warehouse_id": warehouse.id}
        yield ids

        InventoryItem.query.filter_by(id=item.id).delete(synchronize_session=False)
        GrnLine.query.filter_by(id=grn_line.id).delete(synchronize_session=False)
        Grn.query.filter_by(id=grn.id).delete(synchronize_session=False)
        PurchaseOrder.query.filter_by(id=po.id).delete(synchronize_session=False)
        Product.query.filter_by(id=rm.id).delete(synchronize_session=False)
        Warehouse.query.filter_by(id=warehouse.id).delete(synchronize_session=False)
        Party.query.filter_by(id=vendor.id).delete(synchronize_session=False)
        _db.session.commit()


@pytest.fixture
def admin_access(client, fresh_admin):
    resp = client.post("/api/v1/auth/login", json={"email": fresh_admin["email"], "password": fresh_admin["password"]})
    return resp.get_json()["accessToken"]


def test_dispose_returned_to_vendor(client, admin_access, rejected_item):
    headers = {"Authorization": f"Bearer {admin_access}"}
    resp = client.post(f"/api/v1/inventory-items/{rejected_item['item_id']}/dispose", json={"disposition": "returned_to_vendor"}, headers=headers)
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["status"] == "returned_to_vendor"


def test_dispose_discarded(client, admin_access, rejected_item):
    headers = {"Authorization": f"Bearer {admin_access}"}
    resp = client.post(f"/api/v1/inventory-items/{rejected_item['item_id']}/dispose", json={"disposition": "discarded"}, headers=headers)
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["status"] == "discarded"


def test_dispose_twice_is_rejected(client, admin_access, rejected_item):
    headers = {"Authorization": f"Bearer {admin_access}"}
    first = client.post(f"/api/v1/inventory-items/{rejected_item['item_id']}/dispose", json={"disposition": "discarded"}, headers=headers)
    assert first.status_code == 200
    second = client.post(f"/api/v1/inventory-items/{rejected_item['item_id']}/dispose", json={"disposition": "returned_to_vendor"}, headers=headers)
    assert second.status_code == 422
    assert second.get_json()["code"] == "ITEM_NOT_REJECTED"


def test_dispose_rejects_unknown_value(client, admin_access, rejected_item):
    headers = {"Authorization": f"Bearer {admin_access}"}
    resp = client.post(f"/api/v1/inventory-items/{rejected_item['item_id']}/dispose", json={"disposition": "lost"}, headers=headers)
    assert resp.status_code == 400


def test_locationId_filter_on_inventory_items(client, admin_access, rejected_item):
    headers = {"Authorization": f"Bearer {admin_access}"}
    resp = client.get("/api/v1/inventory-items", query_string={"warehouseId": str(rejected_item["warehouse_id"]), "locationId": str(uuid.uuid4())}, headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()["data"] == []
