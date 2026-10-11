"""New coverage - production posting now creates per-unit FinishedGoodItem
rows (the finished-good mirror of InventoryItem) instead of one aggregate
stock-ledger line for the whole run. Piece-per-unit for a UOM=UNIT product,
one lot row otherwise; each item gets its own ledger posting so its
movement history is individually queryable via GET /inventory/ledger?
referenceId=<item id>. No prior test exercised _post_production through the
real API (a full BOM explosion is a hard dependency), so this fixture seeds
a minimal approved BOM with zero components - the finished good needs no
raw materials to produce, which keeps the fixture focused on just the
FG-item behavior being tested."""

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from tests.flaskcompat import db as _db


@pytest.fixture
def producible_fg(app, default_tenant_id):
    from app.models.bom import Bom
    from app.models.bom_version import BomVersion
    from app.models.product import Product
    from app.models.warehouse import Warehouse

    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        unit_fg = Product(tenant_id=default_tenant_id, sku=f"TST-FGU-{suffix}", name="FG Item Test (unit)", type="finished_good", uom="UNIT", status="active")
        lot_fg = Product(tenant_id=default_tenant_id, sku=f"TST-FGL-{suffix}", name="FG Item Test (lot)", type="finished_good", uom="KG", status="active")
        warehouse = Warehouse(tenant_id=default_tenant_id, code=f"WH-FGI-{suffix}", name="FG Item Test Warehouse", status="active")
        warehouse2 = Warehouse(tenant_id=default_tenant_id, code=f"WH-FGI2-{suffix}", name="FG Item Test Warehouse 2", status="active")
        _db.session.add_all([unit_fg, lot_fg, warehouse, warehouse2])
        _db.session.flush()

        boms = []
        for product in (unit_fg, lot_fg):
            bom = Bom(tenant_id=default_tenant_id, product_id=product.id, product_sku=product.sku, status="active")
            _db.session.add(bom)
            _db.session.flush()
            version = BomVersion(tenant_id=default_tenant_id, bom_id=bom.id, version=1, state="approved", yield_percent=100, effective_from=date.today() - timedelta(days=1))
            _db.session.add(version)
            boms.append(bom)
        _db.session.commit()

        ids = {"tenant_id": default_tenant_id, "unit_fg_id": unit_fg.id, "lot_fg_id": lot_fg.id, "unit_fg_sku": unit_fg.sku, "lot_fg_sku": lot_fg.sku, "warehouse_id": warehouse.id, "warehouse2_id": warehouse2.id}
        yield ids

        from app.models.finished_good_item import FinishedGoodItem
        from app.models.production_run import ProductionRun
        from app.models.stock_balance import StockBalance
        from app.models.stock_ledger import StockLedger

        for pid in (unit_fg.id, lot_fg.id):
            FinishedGoodItem.query.filter_by(product_id=pid).delete(synchronize_session=False)
            StockLedger.query.filter_by(product_id=pid).delete(synchronize_session=False)
            StockBalance.query.filter_by(product_id=pid).delete(synchronize_session=False)
            ProductionRun.query.filter_by(product_id=pid).delete(synchronize_session=False)
        BomVersion.query.filter(BomVersion.bom_id.in_([b.id for b in boms])).delete(synchronize_session=False)
        Bom.query.filter(Bom.id.in_([b.id for b in boms])).delete(synchronize_session=False)
        Product.query.filter_by(id=unit_fg.id).delete(synchronize_session=False)
        Product.query.filter_by(id=lot_fg.id).delete(synchronize_session=False)
        Warehouse.query.filter_by(id=warehouse.id).delete(synchronize_session=False)
        Warehouse.query.filter_by(id=warehouse2.id).delete(synchronize_session=False)
        _db.session.commit()


@pytest.fixture
def admin_access(client, fresh_admin):
    resp = client.post("/api/v1/auth/login", json={"email": fresh_admin["email"], "password": fresh_admin["password"]})
    return resp.get_json()["accessToken"]


def test_unit_product_gets_one_finished_good_item_per_piece(app, client, admin_access, producible_fg):
    headers = {"Authorization": f"Bearer {admin_access}"}
    resp = client.post(
        "/api/v1/inventory/production",
        json={"productId": str(producible_fg["unit_fg_id"]), "quantity": "3", "uom": "UNIT", "warehouseId": str(producible_fg["warehouse_id"])},
        headers=headers,
    )
    assert resp.status_code == 201, resp.get_json()

    with app.app_context():
        from app.models.finished_good_item import FinishedGoodItem
        from app.services import inventory_ledger

        items = FinishedGoodItem.query.filter_by(product_id=producible_fg["unit_fg_id"]).order_by(FinishedGoodItem.inventory_id).all()
        assert len(items) == 3
        assert all(i.kind == "piece" for i in items)
        assert all(i.quantity == Decimal("1") for i in items)
        assert all(i.status == "available" for i in items)
        assert all(i.inventory_id.startswith("FG-") for i in items)
        assert len({i.inventory_id for i in items}) == 3  # all distinct

        totals = inventory_ledger.bucket_totals(producible_fg["tenant_id"], producible_fg["unit_fg_id"], producible_fg["warehouse_id"])
        assert Decimal(totals["available"]) == Decimal("3")


def test_lot_product_gets_one_finished_good_item(app, client, admin_access, producible_fg):
    headers = {"Authorization": f"Bearer {admin_access}"}
    resp = client.post(
        "/api/v1/inventory/production",
        json={"productId": str(producible_fg["lot_fg_id"]), "quantity": "12.5", "uom": "KG", "warehouseId": str(producible_fg["warehouse_id"])},
        headers=headers,
    )
    assert resp.status_code == 201, resp.get_json()

    with app.app_context():
        from app.models.finished_good_item import FinishedGoodItem
        from app.services import inventory_ledger

        items = FinishedGoodItem.query.filter_by(product_id=producible_fg["lot_fg_id"]).all()
        assert len(items) == 1
        assert items[0].kind == "lot"
        assert items[0].quantity == Decimal("12.5")

        totals = inventory_ledger.bucket_totals(producible_fg["tenant_id"], producible_fg["lot_fg_id"], producible_fg["warehouse_id"])
        assert Decimal(totals["available"]) == Decimal("12.5")


def test_each_finished_good_item_has_its_own_ledger_history(app, client, admin_access, producible_fg):
    headers = {"Authorization": f"Bearer {admin_access}"}
    resp = client.post(
        "/api/v1/inventory/production",
        json={"productId": str(producible_fg["unit_fg_id"]), "quantity": "2", "uom": "UNIT", "warehouseId": str(producible_fg["warehouse_id"])},
        headers=headers,
    )
    assert resp.status_code == 201

    with app.app_context():
        from app.models.finished_good_item import FinishedGoodItem

        items = FinishedGoodItem.query.filter_by(product_id=producible_fg["unit_fg_id"]).all()
        item_id = str(items[0].id)

    ledger_resp = client.get("/api/v1/inventory/ledger", query_string={"referenceId": item_id}, headers=headers)
    assert ledger_resp.status_code == 200
    rows = ledger_resp.get_json()["data"]
    assert len(rows) == 1
    assert rows[0]["referenceId"] == item_id
    assert rows[0]["movementType"] == "production_output"
    assert Decimal(rows[0]["quantity"]) == Decimal("1")


def _post_two_units(app, client, headers, producible_fg):
    resp = client.post(
        "/api/v1/inventory/production",
        json={"productId": str(producible_fg["unit_fg_id"]), "quantity": "2", "uom": "UNIT", "warehouseId": str(producible_fg["warehouse_id"])},
        headers=headers,
    )
    assert resp.status_code == 201, resp.get_json()
    with app.app_context():
        from app.models.finished_good_item import FinishedGoodItem

        return [str(i.id) for i in FinishedGoodItem.query.filter_by(product_id=producible_fg["unit_fg_id"]).order_by(FinishedGoodItem.inventory_id).all()]


def test_list_and_get_finished_good_items(app, client, admin_access, producible_fg):
    headers = {"Authorization": f"Bearer {admin_access}"}
    item_ids = _post_two_units(app, client, headers, producible_fg)

    list_resp = client.get("/api/v1/inventory/finished-goods", query_string={"productId": str(producible_fg["unit_fg_id"])}, headers=headers)
    assert list_resp.status_code == 200
    data = list_resp.get_json()["data"]
    assert len(data) == 2
    assert all(row["status"] == "available" for row in data)
    assert all(row["availableQty"] == "1.000000" for row in data)

    get_resp = client.get(f"/api/v1/inventory/finished-goods/{item_ids[0]}", headers=headers)
    assert get_resp.status_code == 200
    detail = get_resp.get_json()
    assert detail["id"] == item_ids[0]
    assert detail["warehouseName"]
    assert detail["productionRunNumber"].startswith("PRD-")


def test_get_missing_finished_good_item_is_404(client, admin_access):
    resp = client.get(f"/api/v1/inventory/finished-goods/{uuid.uuid4()}", headers={"Authorization": f"Bearer {admin_access}"})
    assert resp.status_code == 404


def test_transfer_finished_good_item_moves_stock_and_updates_item(app, client, admin_access, producible_fg):
    headers = {"Authorization": f"Bearer {admin_access}"}
    item_ids = _post_two_units(app, client, headers, producible_fg)

    resp = client.post(f"/api/v1/inventory/finished-goods/{item_ids[0]}/transfer", json={"toWarehouseId": str(producible_fg["warehouse2_id"])}, headers=headers)
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["warehouseId"] == str(producible_fg["warehouse2_id"])

    with app.app_context():
        from app.services import inventory_ledger

        source_totals = inventory_ledger.bucket_totals(producible_fg["tenant_id"], producible_fg["unit_fg_id"], producible_fg["warehouse_id"])
        dest_totals = inventory_ledger.bucket_totals(producible_fg["tenant_id"], producible_fg["unit_fg_id"], producible_fg["warehouse2_id"])
        assert Decimal(source_totals["available"]) == Decimal("1")  # the other unit stayed
        assert Decimal(dest_totals["available"]) == Decimal("1")

    # Both transfer legs must be queryable by the item's own id - this is
    # what the FG detail dialog's movement-history table relies on.
    ledger_resp = client.get("/api/v1/inventory/ledger", query_string={"referenceId": item_ids[0]}, headers=headers)
    assert ledger_resp.status_code == 200
    rows = ledger_resp.get_json()["data"]
    movement_types = {r["movementType"] for r in rows}
    assert {"production_output", "transfer_out", "transfer_in"} <= movement_types


def test_change_finished_good_item_status(app, client, admin_access, producible_fg):
    headers = {"Authorization": f"Bearer {admin_access}"}
    item_ids = _post_two_units(app, client, headers, producible_fg)

    resp = client.post(f"/api/v1/inventory/finished-goods/{item_ids[0]}/status", json={"toStatus": "quarantine"}, headers=headers)
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["status"] == "quarantine"

    with app.app_context():
        from app.services import inventory_ledger

        totals = inventory_ledger.bucket_totals(producible_fg["tenant_id"], producible_fg["unit_fg_id"], producible_fg["warehouse_id"])
        assert Decimal(totals["available"]) == Decimal("1")
        assert Decimal(totals["quarantine"]) == Decimal("1")

    # Both status-change legs must be queryable by the item's own id - this
    # is what the FG detail dialog's movement-history table relies on.
    ledger_resp = client.get("/api/v1/inventory/ledger", query_string={"referenceId": item_ids[0]}, headers=headers)
    assert ledger_resp.status_code == 200
    rows = ledger_resp.get_json()["data"]
    status_change_rows = [r for r in rows if r["movementType"] == "status_change"]
    assert len(status_change_rows) == 2
    assert {r["bucket"] for r in status_change_rows} == {"available", "quarantine"}

    # Same status again is a no-op error, not a silent success.
    noop_resp = client.post(f"/api/v1/inventory/finished-goods/{item_ids[0]}/status", json={"toStatus": "quarantine"}, headers=headers)
    assert noop_resp.status_code == 422
    assert noop_resp.get_json()["code"] == "STATUS_CHANGE_NOOP"


def test_production_run_list_and_detail_include_product_name_and_finished_goods(app, client, admin_access, producible_fg):
    """New coverage for the Production module's detail-screen redesign:
    productName (for "SKU Name" columns) and finishedGoods (the "Finished
    Goods Produced" section, listing the FG-IDs this run actually made)."""
    headers = {"Authorization": f"Bearer {admin_access}"}
    resp = client.post(
        "/api/v1/inventory/production",
        json={"productId": str(producible_fg["unit_fg_id"]), "quantity": "2", "uom": "UNIT", "warehouseId": str(producible_fg["warehouse_id"])},
        headers=headers,
    )
    assert resp.status_code == 201, resp.get_json()
    run_id = resp.get_json()["id"]

    list_resp = client.get("/api/v1/inventory/production", query_string={"productId": str(producible_fg["unit_fg_id"])}, headers=headers)
    assert list_resp.status_code == 200
    rows = list_resp.get_json()["data"]
    assert any(r["id"] == run_id for r in rows)
    assert next(r for r in rows if r["id"] == run_id)["productName"] == "FG Item Test (unit)"

    detail_resp = client.get(f"/api/v1/inventory/production/{run_id}", headers=headers)
    assert detail_resp.status_code == 200
    detail = detail_resp.get_json()
    assert detail["productName"] == "FG Item Test (unit)"
    assert len(detail["finishedGoods"]) == 2
    assert all(fg["inventoryId"].startswith("FG-") for fg in detail["finishedGoods"])
    assert all(fg["kind"] == "piece" for fg in detail["finishedGoods"])
