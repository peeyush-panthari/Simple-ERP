"""POST /inventory/adjustments with itemId - writing off or adding back
stock against a specific, hand-picked Inventory ID must actually move that
physical unit's own written_off_qty (or reverse it / bump accepted_qty),
without disturbing consumed_qty (production) or accepted_qty in a way that
would corrupt the GRN-accepted figure other code already relies on."""

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
        rm = Product(tenant_id=default_tenant_id, sku=f"TST-ADJ-{suffix}", name="Adjustment Test RM", type="raw_material", uom="KG", status="active")
        wh = Warehouse(tenant_id=default_tenant_id, code=f"WH-ADJ-{suffix}", name="Adjustment Test WH", status="active")
        vendor = Party(tenant_id=default_tenant_id, code=f"VEN-ADJ-{suffix}", legal_name="Adjustment Test Vendor Ltd", display_name="Adjustment Test Vendor", type="vendor", status="active")
        _db.session.add_all([rm, wh, vendor])
        _db.session.flush()

        po = PurchaseOrder(tenant_id=default_tenant_id, number=f"PO-ADJ-{suffix}", vendor_id=vendor.id, vendor_name=vendor.display_name, warehouse_id=wh.id, warehouse_code=wh.code, expected_date="2027-01-01")
        _db.session.add(po)
        _db.session.flush()
        grn = Grn(tenant_id=default_tenant_id, number=f"GRN-ADJ-{suffix}", po_id=po.id, warehouse_id=wh.id)
        _db.session.add(grn)
        _db.session.flush()
        grn_line = GrnLine(tenant_id=default_tenant_id, grn_id=grn.id, line_no=1, product_id=rm.id, sku=rm.sku, received_qty="10", accepted_qty="10", uom="KG", unit_price="5")
        _db.session.add(grn_line)
        _db.session.flush()
        item = InventoryItem(tenant_id=default_tenant_id, inventory_id=f"INV-ADJ-{suffix}", grn_id=grn.id, grn_line_id=grn_line.id, product_id=rm.id, sku=rm.sku, warehouse_id=wh.id, status="accepted", kind="lot", quantity="10", uom="KG", accepted_qty="10", received_date=date.today())
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


def _adjustment_body(fx, **overrides):
    body = {
        "productId": str(fx["product_id"]),
        "warehouseId": str(fx["warehouse_id"]),
        "batchNo": None,
        "quantity": "-4",
        "uom": "KG",
        "bucket": "available",
        "reason": "Cycle count found a shortage against this lot",
        "itemId": str(fx["item_id"]),
    }
    body.update(overrides)
    return body


def test_write_off_against_item_increases_its_written_off_qty(app, client, admin_access, item_and_warehouse):
    fx = item_and_warehouse
    headers = {"Authorization": f"Bearer {admin_access}"}
    resp = client.post("/api/v1/inventory/adjustments", json=_adjustment_body(fx), headers=headers)
    assert resp.status_code == 201, resp.get_json()

    get_resp = client.get(f"/api/v1/inventory-items/{fx['item_id']}", headers=headers)
    body = get_resp.get_json()
    assert body["writtenOffQty"] == "4.000000"
    assert body["acceptedQty"] == "10.000000"
    assert body["availableQty"] == "6.000000"


def test_partial_write_off_is_allowed_unlike_transfer(client, admin_access, item_and_warehouse):
    fx = item_and_warehouse
    headers = {"Authorization": f"Bearer {admin_access}"}
    resp = client.post("/api/v1/inventory/adjustments", json=_adjustment_body(fx, quantity="-2"), headers=headers)
    assert resp.status_code == 201, resp.get_json()


def test_write_off_exceeding_available_is_rejected(client, admin_access, item_and_warehouse):
    fx = item_and_warehouse
    headers = {"Authorization": f"Bearer {admin_access}"}
    resp = client.post("/api/v1/inventory/adjustments", json=_adjustment_body(fx, quantity="-11"), headers=headers)
    assert resp.status_code == 422
    assert resp.get_json()["code"] == "ADJUSTMENT_INVALID"


def test_fully_written_off_item_excluded_from_available_and_shows_in_written_off_filter(app, client, admin_access, item_and_warehouse):
    fx = item_and_warehouse
    headers = {"Authorization": f"Bearer {admin_access}"}
    resp = client.post("/api/v1/inventory/adjustments", json=_adjustment_body(fx, quantity="-10"), headers=headers)
    assert resp.status_code == 201

    list_resp = client.get("/api/v1/inventory-items", query_string={"productId": str(fx["product_id"]), "available": "true"}, headers=headers)
    ids = {r["id"] for r in list_resp.get_json()["data"]}
    assert str(fx["item_id"]) not in ids

    written_off_resp = client.get("/api/v1/inventory-items", query_string={"productId": str(fx["product_id"]), "writtenOff": "true"}, headers=headers)
    ids = {r["id"] for r in written_off_resp.get_json()["data"]}
    assert str(fx["item_id"]) in ids


def test_positive_adjustment_reverses_write_off_before_bumping_accepted_qty(app, client, admin_access, item_and_warehouse):
    fx = item_and_warehouse
    headers = {"Authorization": f"Bearer {admin_access}"}
    # Write off 4, then add back 6 - 4 should reverse the write-off, the
    # remaining 2 should bump accepted_qty (a genuine recount surplus).
    write_off = client.post("/api/v1/inventory/adjustments", json=_adjustment_body(fx, quantity="-4"), headers=headers)
    assert write_off.status_code == 201

    add_back = client.post("/api/v1/inventory/adjustments", json=_adjustment_body(fx, quantity="6"), headers=headers)
    assert add_back.status_code == 201, add_back.get_json()

    get_resp = client.get(f"/api/v1/inventory-items/{fx['item_id']}", headers=headers)
    body = get_resp.get_json()
    assert body["writtenOffQty"] == "0.000000"
    assert body["acceptedQty"] == "12.000000"


def test_write_off_does_not_touch_accepted_qty_or_consumed_qty(app, client, admin_access, item_and_warehouse):
    fx = item_and_warehouse
    headers = {"Authorization": f"Bearer {admin_access}"}
    resp = client.post("/api/v1/inventory/adjustments", json=_adjustment_body(fx, quantity="-3"), headers=headers)
    assert resp.status_code == 201

    get_resp = client.get(f"/api/v1/inventory-items/{fx['item_id']}", headers=headers)
    body = get_resp.get_json()
    assert body["acceptedQty"] == "10.000000"
    assert body["consumedQty"] == "0.000000"


def test_bucket_mismatch_against_a_picked_item_is_rejected(client, admin_access, item_and_warehouse):
    fx = item_and_warehouse
    headers = {"Authorization": f"Bearer {admin_access}"}
    resp = client.post("/api/v1/inventory/adjustments", json=_adjustment_body(fx, bucket="damaged"), headers=headers)
    assert resp.status_code == 422
    assert resp.get_json()["code"] == "ADJUSTMENT_INVALID"
