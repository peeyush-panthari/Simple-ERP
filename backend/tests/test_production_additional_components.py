"""New coverage for add/remove on a posted run's "Additional raw materials
(beyond BOM)" - POST/DELETE /inventory/production/<id>/additional-components.
Exercises real stock: an add must actually draw the ledger (and, for a
manually-picked Inventory ID, InventoryItem.consumed_qty), and a remove must
precisely reverse both - the whole point of production_consumption_items."""

import uuid
from decimal import Decimal

import pytest

from tests.flaskcompat import db as _db


@pytest.fixture
def stocked_run(app, default_tenant_id):
    """A posted finished-good run plus a raw material with 10 KG of real,
    Inventory-ID-tracked stock available to consume as an additional
    component - a minimal but real GRN-receiving chain (Party -> PO -> GRN
    -> GrnLine -> InventoryItem), since nothing in this codebase constructs
    one directly yet."""
    from app.models.grn import Grn
    from app.models.grn_line import GrnLine
    from app.models.inventory_item import InventoryItem
    from app.models.party import Party
    from app.models.product import Product
    from app.models.production_run import ProductionRun
    from app.models.purchase_order import PurchaseOrder
    from app.models.warehouse import Warehouse
    from app.services import inventory_ledger
    from app.services.inventory_ledger import LedgerPosting

    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        fg = Product(tenant_id=default_tenant_id, sku=f"TST-FG-{suffix}", name="Additional-Component Test FG", type="finished_good", uom="UNIT", status="active")
        rm = Product(tenant_id=default_tenant_id, sku=f"TST-RM-{suffix}", name="Additional-Component Test RM", type="raw_material", uom="KG", status="active")
        warehouse = Warehouse(tenant_id=default_tenant_id, code=f"WH-AC-{suffix}", name="Additional-Component Test Warehouse", status="active")
        vendor = Party(tenant_id=default_tenant_id, code=f"VEN-{suffix}", legal_name="Test Vendor Ltd", display_name="Test Vendor", type="vendor", status="active")
        _db.session.add_all([fg, rm, warehouse, vendor])
        _db.session.flush()

        po = PurchaseOrder(tenant_id=default_tenant_id, number=f"PO-AC-{suffix}", vendor_id=vendor.id, vendor_name=vendor.display_name, warehouse_id=warehouse.id, warehouse_code=warehouse.code, expected_date="2027-01-01")
        _db.session.add(po)
        _db.session.flush()
        grn = Grn(tenant_id=default_tenant_id, number=f"GRN-AC-{suffix}", po_id=po.id, warehouse_id=warehouse.id)
        _db.session.add(grn)
        _db.session.flush()
        grn_line = GrnLine(tenant_id=default_tenant_id, grn_id=grn.id, line_no=1, product_id=rm.id, sku=rm.sku, received_qty="10", accepted_qty="10", uom="KG")
        _db.session.add(grn_line)
        _db.session.flush()
        item = InventoryItem(tenant_id=default_tenant_id, inventory_id=f"INV-AC-{suffix}", grn_id=grn.id, grn_line_id=grn_line.id, product_id=rm.id, sku=rm.sku, warehouse_id=warehouse.id, status="accepted", kind="lot", quantity="10", uom="KG", accepted_qty="10")
        _db.session.add(item)

        run = ProductionRun(tenant_id=default_tenant_id, number=f"PRD-AC-{suffix}", product_id=fg.id, sku=fg.sku, quantity="1", uom="UNIT", warehouse_id=warehouse.id)
        _db.session.add(run)
        _db.session.flush()

        inventory_ledger.post(
            LedgerPosting(
                tenant_id=default_tenant_id,
                product_id=rm.id,
                sku=rm.sku,
                warehouse_id=warehouse.id,
                quantity="10",
                uom="KG",
                bucket="available",
                movement_type="receipt",
                reference_type="test-fixture",
                reference_id=f"fixture-{suffix}",
            )
        )
        _db.session.commit()
        ids = {"tenant_id": default_tenant_id, "run_id": run.id, "product_id": rm.id, "item_id": item.id, "warehouse_id": warehouse.id, "sku": rm.sku}
        yield ids

        from app.models.stock_balance import StockBalance
        from app.models.stock_ledger import StockLedger
        from app.models.production_consumption import ProductionConsumption
        from app.models.production_consumption_item import ProductionConsumptionItem

        consumption_ids = [c.id for c in ProductionConsumption.query.filter_by(production_run_id=run.id).all()]
        if consumption_ids:
            ProductionConsumptionItem.query.filter(ProductionConsumptionItem.production_consumption_id.in_(consumption_ids)).delete(synchronize_session=False)
        ProductionConsumption.query.filter_by(production_run_id=run.id).delete(synchronize_session=False)
        ProductionRun.query.filter_by(id=run.id).delete(synchronize_session=False)
        StockLedger.query.filter_by(product_id=rm.id).delete(synchronize_session=False)
        StockBalance.query.filter_by(product_id=rm.id).delete(synchronize_session=False)
        InventoryItem.query.filter_by(id=item.id).delete(synchronize_session=False)
        GrnLine.query.filter_by(id=grn_line.id).delete(synchronize_session=False)
        Grn.query.filter_by(id=grn.id).delete(synchronize_session=False)
        PurchaseOrder.query.filter_by(id=po.id).delete(synchronize_session=False)
        Product.query.filter_by(id=fg.id).delete(synchronize_session=False)
        Product.query.filter_by(id=rm.id).delete(synchronize_session=False)
        Warehouse.query.filter_by(id=warehouse.id).delete(synchronize_session=False)
        Party.query.filter_by(id=vendor.id).delete(synchronize_session=False)
        _db.session.commit()


@pytest.fixture
def admin_access(client, fresh_admin):
    resp = client.post("/api/v1/auth/login", json={"email": fresh_admin["email"], "password": fresh_admin["password"]})
    return resp.get_json()["accessToken"]


def _available_kg(app, tenant_id, product_id, warehouse_id):
    from app.services import inventory_ledger

    with app.app_context():
        totals = inventory_ledger.bucket_totals(tenant_id, product_id, warehouse_id)
        return Decimal(totals["available"])


def test_add_then_remove_additional_component_restores_stock_and_item(app, client, admin_access, stocked_run):
    run_id = stocked_run["run_id"]
    headers = {"Authorization": f"Bearer {admin_access}"}

    add_resp = client.post(
        f"/api/v1/inventory/production/{run_id}/additional-components",
        json={"productId": str(stocked_run["product_id"]), "quantity": "3", "uom": "KG", "items": [{"itemId": str(stocked_run["item_id"]), "productId": str(stocked_run["product_id"]), "quantity": "3"}]},
        headers=headers,
    )
    assert add_resp.status_code == 200, add_resp.get_json()
    consumed = add_resp.get_json()
    assert len(consumed) == 1
    row = consumed[0]
    assert row["isAdditional"] is True
    assert row["removable"] is True
    assert Decimal(row["quantity"]) == Decimal("3")
    assert row["sku"] == stocked_run["sku"]

    assert _available_kg(app, stocked_run["tenant_id"], stocked_run["product_id"], stocked_run["warehouse_id"]) == Decimal("7")
    with app.app_context():
        from app.models.inventory_item import InventoryItem

        item = InventoryItem.query.filter_by(id=stocked_run["item_id"]).first()
        assert item.consumed_qty == Decimal("3")

    remove_resp = client.delete(f"/api/v1/inventory/production/{run_id}/additional-components/{row['id']}", headers=headers)
    assert remove_resp.status_code == 200, remove_resp.get_json()
    assert remove_resp.get_json() == []

    assert _available_kg(app, stocked_run["tenant_id"], stocked_run["product_id"], stocked_run["warehouse_id"]) == Decimal("10")
    with app.app_context():
        from app.models.inventory_item import InventoryItem

        item = InventoryItem.query.filter_by(id=stocked_run["item_id"]).first()
        assert item.consumed_qty == Decimal("0")
        assert item.consumed_run_id is None


def test_add_rejects_insufficient_stock(client, admin_access, stocked_run):
    resp = client.post(
        f"/api/v1/inventory/production/{stocked_run['run_id']}/additional-components",
        json={"productId": str(stocked_run["product_id"]), "quantity": "999", "uom": "KG"},
        headers={"Authorization": f"Bearer {admin_access}"},
    )
    assert resp.status_code == 422
    assert resp.get_json()["code"] == "INSUFFICIENT_COMPONENTS"


def test_pre_existing_additional_component_is_not_removable(app, client, admin_access, stocked_run):
    """Simulates a component added by the original create flow - a
    production_consumption row with no production_consumption_items and no
    matching ledger reference_id - which must report removable: false and
    reject a delete attempt outright."""
    from app.models.production_consumption import ProductionConsumption

    with app.app_context():
        legacy = ProductionConsumption(tenant_id=stocked_run["tenant_id"], production_run_id=stocked_run["run_id"], product_id=stocked_run["product_id"], sku=stocked_run["sku"], quantity="2", uom="KG", is_additional=True)
        _db.session.add(legacy)
        _db.session.commit()
        legacy_id = legacy.id

    headers = {"Authorization": f"Bearer {admin_access}"}
    get_resp = client.get(f"/api/v1/inventory/production/{stocked_run['run_id']}", headers=headers)
    row = next(c for c in get_resp.get_json()["consumed"] if c["id"] == str(legacy_id))
    assert row["removable"] is False

    delete_resp = client.delete(f"/api/v1/inventory/production/{stocked_run['run_id']}/additional-components/{legacy_id}", headers=headers)
    assert delete_resp.status_code == 422
    assert delete_resp.get_json()["code"] == "ADDITIONAL_COMPONENT_NOT_REMOVABLE"

    with app.app_context():
        ProductionConsumption.query.filter_by(id=legacy_id).delete(synchronize_session=False)
        _db.session.commit()


def test_remove_missing_consumption_is_404(client, admin_access, stocked_run):
    resp = client.delete(
        f"/api/v1/inventory/production/{stocked_run['run_id']}/additional-components/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {admin_access}"},
    )
    assert resp.status_code == 404
