"""POST /inventory/status-change with itemId - moving a specific, hand-picked
Inventory ID into quarantine/damaged/expired must actually move that
physical unit's own bucket (and therefore its displayed status/availability),
not just post a product+batch+quantity ledger pair that leaves the item's
own record untouched."""

import uuid
from datetime import date

import pytest

from tests.flaskcompat import db as _db


@pytest.fixture
def item_and_warehouse(app, default_tenant_id):
    from app.models.grn import Grn
    from app.models.grn_line import GrnLine
    from app.models.inventory_item import InventoryItem
    from app.models.party import Party
    from app.models.product import Product
    from app.models.purchase_order import PurchaseOrder
    from app.models.warehouse import Warehouse

    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        rm = Product(tenant_id=default_tenant_id, sku=f"TST-STS-{suffix}", name="Status Change Test RM", type="raw_material", uom="KG", status="active")
        wh = Warehouse(tenant_id=default_tenant_id, code=f"WH-STS-{suffix}", name="Status Change Test WH", status="active")
        vendor = Party(tenant_id=default_tenant_id, code=f"VEN-STS-{suffix}", legal_name="Status Change Test Vendor Ltd", display_name="Status Change Test Vendor", type="vendor", status="active")
        _db.session.add_all([rm, wh, vendor])
        _db.session.flush()

        po = PurchaseOrder(tenant_id=default_tenant_id, number=f"PO-STS-{suffix}", vendor_id=vendor.id, vendor_name=vendor.display_name, warehouse_id=wh.id, warehouse_code=wh.code, expected_date="2027-01-01")
        _db.session.add(po)
        _db.session.flush()
        grn = Grn(tenant_id=default_tenant_id, number=f"GRN-STS-{suffix}", po_id=po.id, warehouse_id=wh.id)
        _db.session.add(grn)
        _db.session.flush()
        grn_line = GrnLine(tenant_id=default_tenant_id, grn_id=grn.id, line_no=1, product_id=rm.id, sku=rm.sku, received_qty="10", accepted_qty="10", uom="KG", unit_price="5")
        _db.session.add(grn_line)
        _db.session.flush()
        item = InventoryItem(tenant_id=default_tenant_id, inventory_id=f"INV-STS-{suffix}", grn_id=grn.id, grn_line_id=grn_line.id, product_id=rm.id, sku=rm.sku, warehouse_id=wh.id, status="accepted", kind="lot", quantity="10", uom="KG", accepted_qty="10", received_date=date.today())
        _db.session.add(item)
        _db.session.commit()

        from app.services import inventory_ledger
        from app.services.inventory_ledger import LedgerPosting

        inventory_ledger.post(
            LedgerPosting(
                tenant_id=default_tenant_id,
                product_id=rm.id,
                sku=rm.sku,
                warehouse_id=wh.id,
                quantity="10",
                uom="KG",
                bucket="available",
                movement_type="receipt",
                reference_type="test-fixture",
                reference_id=f"fixture-{item.id}",
                unit_cost="5",
            )
        )
        _db.session.commit()

        ids = {"tenant_id": default_tenant_id, "product_id": rm.id, "sku": rm.sku, "item_id": item.id, "warehouse_id": wh.id}
        yield ids

        from app.models.stock_balance import StockBalance
        from app.models.stock_ledger import StockLedger

        InventoryItem.query.filter_by(id=item.id).delete(synchronize_session=False)
        GrnLine.query.filter_by(id=grn_line.id).delete(synchronize_session=False)
        Grn.query.filter_by(id=grn.id).delete(synchronize_session=False)
        PurchaseOrder.query.filter_by(id=po.id).delete(synchronize_session=False)
        StockLedger.query.filter_by(product_id=rm.id).delete(synchronize_session=False)
        StockBalance.query.filter_by(product_id=rm.id).delete(synchronize_session=False)
        Product.query.filter_by(id=rm.id).delete(synchronize_session=False)
        Warehouse.query.filter_by(id=wh.id).delete(synchronize_session=False)
        Party.query.filter_by(id=vendor.id).delete(synchronize_session=False)
        _db.session.commit()


@pytest.fixture
def admin_access(client, fresh_admin):
    resp = client.post("/api/v1/auth/login", json={"email": fresh_admin["email"], "password": fresh_admin["password"]})
    return resp.get_json()["accessToken"]


def _status_change_body(fx, **overrides):
    body = {
        "productId": str(fx["product_id"]),
        "warehouseId": str(fx["warehouse_id"]),
        "batchNo": None,
        "quantity": "10",
        "uom": "KG",
        "from": "available",
        "to": "quarantine",
        "reason": "QC recall - moving to quarantine for re-inspection",
        "itemId": str(fx["item_id"]),
    }
    body.update(overrides)
    return body


def test_status_change_by_item_moves_the_item_bucket_immediately(app, client, admin_access, item_and_warehouse):
    fx = item_and_warehouse
    headers = {"Authorization": f"Bearer {admin_access}"}
    resp = client.post("/api/v1/inventory/status-change", json=_status_change_body(fx), headers=headers)
    assert resp.status_code == 201, resp.get_json()

    get_resp = client.get(f"/api/v1/inventory-items/{fx['item_id']}", headers=headers)
    body = get_resp.get_json()
    assert body["bucket"] == "quarantine"


def test_status_change_by_item_excludes_it_from_available_filter(app, client, admin_access, item_and_warehouse):
    fx = item_and_warehouse
    headers = {"Authorization": f"Bearer {admin_access}"}
    resp = client.post("/api/v1/inventory/status-change", json=_status_change_body(fx), headers=headers)
    assert resp.status_code == 201

    list_resp = client.get("/api/v1/inventory-items", query_string={"productId": str(fx["product_id"]), "available": "true"}, headers=headers)
    ids = {r["id"] for r in list_resp.get_json()["data"]}
    assert str(fx["item_id"]) not in ids

    bucket_resp = client.get("/api/v1/inventory-items", query_string={"productId": str(fx["product_id"]), "bucket": "quarantine"}, headers=headers)
    ids = {r["id"] for r in bucket_resp.get_json()["data"]}
    assert str(fx["item_id"]) in ids


def test_moving_the_item_back_to_available_releases_it(app, client, admin_access, item_and_warehouse):
    fx = item_and_warehouse
    headers = {"Authorization": f"Bearer {admin_access}"}
    resp = client.post("/api/v1/inventory/status-change", json=_status_change_body(fx), headers=headers)
    assert resp.status_code == 201

    back = client.post(
        "/api/v1/inventory/status-change",
        json=_status_change_body(fx, **{"from": "quarantine", "to": "available", "reason": "Re-inspected and cleared"}),
        headers=headers,
    )
    assert back.status_code == 201, back.get_json()

    get_resp = client.get(f"/api/v1/inventory-items/{fx['item_id']}", headers=headers)
    assert get_resp.get_json()["bucket"] == "available"

    list_resp = client.get("/api/v1/inventory-items", query_string={"productId": str(fx["product_id"]), "available": "true"}, headers=headers)
    ids = {r["id"] for r in list_resp.get_json()["data"]}
    assert str(fx["item_id"]) in ids


def test_partial_quantity_against_a_picked_item_is_rejected(client, admin_access, item_and_warehouse):
    fx = item_and_warehouse
    headers = {"Authorization": f"Bearer {admin_access}"}
    resp = client.post("/api/v1/inventory/status-change", json=_status_change_body(fx, quantity="4"), headers=headers)
    assert resp.status_code == 422
    assert resp.get_json()["code"] == "STATUS_CHANGE_INVALID"


def test_wrong_from_bucket_against_a_picked_item_is_rejected(client, admin_access, item_and_warehouse):
    fx = item_and_warehouse
    headers = {"Authorization": f"Bearer {admin_access}"}
    resp = client.post("/api/v1/inventory/status-change", json=_status_change_body(fx, **{"from": "damaged"}), headers=headers)
    assert resp.status_code == 422
    assert resp.get_json()["code"] == "STATUS_CHANGE_INVALID"


def test_already_moved_item_cannot_be_moved_from_available_again(client, admin_access, item_and_warehouse):
    fx = item_and_warehouse
    headers = {"Authorization": f"Bearer {admin_access}"}
    first = client.post("/api/v1/inventory/status-change", json=_status_change_body(fx), headers=headers)
    assert first.status_code == 201

    second = client.post("/api/v1/inventory/status-change", json=_status_change_body(fx), headers=headers)
    assert second.status_code == 422
    assert second.get_json()["code"] == "STATUS_CHANGE_INVALID"
