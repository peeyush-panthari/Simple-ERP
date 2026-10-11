"""Finished-good output now gets priced at production time from what its
consumed raw materials actually cost (each raw material's own weighted-
average cost, from its receipt history) - previously every production_output
ledger posting carried unit_cost=None, so Finished Goods always valued at
zero regardless of on-hand quantity. Covers the BOM-required component path,
the additional-(beyond-BOM)-component path, and that Finished Goods
valuation (compute_valuation / GET /inventory/valuation) reflects it."""

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from tests.flaskcompat import db as _db


@pytest.fixture
def costed_bom(app, default_tenant_id):
    """A FG with a one-line BOM (2 KG of RM per unit), RM stocked via a
    costed receipt (10 KG @ 50/KG)."""
    from app.models.bom import Bom
    from app.models.bom_component import BomComponent
    from app.models.bom_version import BomVersion
    from app.models.product import Product
    from app.models.warehouse import Warehouse
    from app.services import inventory_ledger
    from app.services.inventory_ledger import LedgerPosting

    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        fg = Product(tenant_id=default_tenant_id, sku=f"TST-COST-FG-{suffix}", name="Costing Test FG", type="finished_good", uom="UNIT", status="active")
        rm = Product(tenant_id=default_tenant_id, sku=f"TST-COST-RM-{suffix}", name="Costing Test RM", type="raw_material", uom="KG", status="active")
        rm2 = Product(tenant_id=default_tenant_id, sku=f"TST-COST-RM2-{suffix}", name="Costing Test RM (extra)", type="raw_material", uom="KG", status="active")
        warehouse = Warehouse(tenant_id=default_tenant_id, code=f"WH-COST-{suffix}", name="Costing Test Warehouse", status="active")
        _db.session.add_all([fg, rm, rm2, warehouse])
        _db.session.flush()

        bom = Bom(tenant_id=default_tenant_id, product_id=fg.id, product_sku=fg.sku, status="active")
        _db.session.add(bom)
        _db.session.flush()
        version = BomVersion(tenant_id=default_tenant_id, bom_id=bom.id, version=1, state="approved", yield_percent=100, effective_from=date.today() - timedelta(days=1))
        _db.session.add(version)
        _db.session.flush()
        component = BomComponent(tenant_id=default_tenant_id, bom_version_id=version.id, line_no=1, component_product_id=rm.id, component_sku=rm.sku, quantity="2", uom="KG")
        _db.session.add(component)
        _db.session.flush()

        for product, qty, unit_cost in ((rm, "10", "50"), (rm2, "10", "20")):
            inventory_ledger.post(
                LedgerPosting(
                    tenant_id=default_tenant_id,
                    product_id=product.id,
                    sku=product.sku,
                    warehouse_id=warehouse.id,
                    quantity=qty,
                    uom="KG",
                    bucket="available",
                    movement_type="receipt",
                    reference_type="test-fixture",
                    reference_id=f"fixture-{product.id}",
                    unit_cost=unit_cost,
                )
            )
        _db.session.commit()

        ids = {"tenant_id": default_tenant_id, "fg_id": fg.id, "fg_sku": fg.sku, "rm_id": rm.id, "rm2_id": rm2.id, "warehouse_id": warehouse.id}
        yield ids

        from app.models.finished_good_item import FinishedGoodItem
        from app.models.production_consumption import ProductionConsumption
        from app.models.production_run import ProductionRun
        from app.models.stock_balance import StockBalance
        from app.models.stock_ledger import StockLedger

        run_ids = [r.id for r in ProductionRun.query.filter_by(product_id=fg.id).all()]
        if run_ids:
            ProductionConsumption.query.filter(ProductionConsumption.production_run_id.in_(run_ids)).delete(synchronize_session=False)
        FinishedGoodItem.query.filter_by(product_id=fg.id).delete(synchronize_session=False)
        ProductionRun.query.filter_by(product_id=fg.id).delete(synchronize_session=False)
        StockLedger.query.filter(StockLedger.product_id.in_([fg.id, rm.id, rm2.id])).delete(synchronize_session=False)
        StockBalance.query.filter(StockBalance.product_id.in_([fg.id, rm.id, rm2.id])).delete(synchronize_session=False)
        BomComponent.query.filter_by(bom_version_id=version.id).delete(synchronize_session=False)
        BomVersion.query.filter_by(bom_id=bom.id).delete(synchronize_session=False)
        Bom.query.filter_by(id=bom.id).delete(synchronize_session=False)
        Product.query.filter_by(id=fg.id).delete(synchronize_session=False)
        Product.query.filter_by(id=rm.id).delete(synchronize_session=False)
        Product.query.filter_by(id=rm2.id).delete(synchronize_session=False)
        Warehouse.query.filter_by(id=warehouse.id).delete(synchronize_session=False)
        _db.session.commit()


@pytest.fixture
def costed_bom_with_picked_items(app, default_tenant_id):
    """A FG whose BOM needs 2 UNIT of an RM that has two real, GRN-receipted
    Inventory IDs at very different costs (10 and 100/unit) - so picking one
    specific item over the other should change the finished good's costed
    output, proving it prices off the actual pick rather than an average
    across the product's whole receipt history."""
    from app.models.bom import Bom
    from app.models.bom_component import BomComponent
    from app.models.bom_version import BomVersion
    from app.models.grn import Grn
    from app.models.grn_line import GrnLine
    from app.models.inventory_item import InventoryItem
    from app.models.party import Party
    from app.models.product import Product
    from app.models.purchase_order import PurchaseOrder
    from app.models.warehouse import Warehouse

    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        fg = Product(tenant_id=default_tenant_id, sku=f"TST-COSTPICK-FG-{suffix}", name="Costed-Pick Test FG", type="finished_good", uom="UNIT", status="active")
        rm = Product(tenant_id=default_tenant_id, sku=f"TST-COSTPICK-RM-{suffix}", name="Costed-Pick Test RM", type="raw_material", uom="UNIT", status="active")
        warehouse = Warehouse(tenant_id=default_tenant_id, code=f"WH-COSTPICK-{suffix}", name="Costed-Pick Test Warehouse", status="active")
        vendor = Party(tenant_id=default_tenant_id, code=f"VEN-CP-{suffix}", legal_name="Costed-Pick Test Vendor Ltd", display_name="Costed-Pick Test Vendor", type="vendor", status="active")
        _db.session.add_all([fg, rm, warehouse, vendor])
        _db.session.flush()

        bom = Bom(tenant_id=default_tenant_id, product_id=fg.id, product_sku=fg.sku, status="active")
        _db.session.add(bom)
        _db.session.flush()
        version = BomVersion(tenant_id=default_tenant_id, bom_id=bom.id, version=1, state="approved", yield_percent=100, effective_from=date.today() - timedelta(days=1))
        _db.session.add(version)
        _db.session.flush()
        component = BomComponent(tenant_id=default_tenant_id, bom_version_id=version.id, line_no=1, component_product_id=rm.id, component_sku=rm.sku, quantity="2", uom="UNIT")
        _db.session.add(component)
        _db.session.flush()

        po = PurchaseOrder(tenant_id=default_tenant_id, number=f"PO-CP-{suffix}", vendor_id=vendor.id, vendor_name=vendor.display_name, warehouse_id=warehouse.id, warehouse_code=warehouse.code, expected_date="2027-01-01")
        _db.session.add(po)
        _db.session.flush()
        grn = Grn(tenant_id=default_tenant_id, number=f"GRN-CP-{suffix}", po_id=po.id, warehouse_id=warehouse.id)
        _db.session.add(grn)
        _db.session.flush()

        items = {}
        for label, unit_price in (("cheap", "10"), ("pricey", "100")):
            grn_line = GrnLine(tenant_id=default_tenant_id, grn_id=grn.id, line_no=1 if label == "cheap" else 2, product_id=rm.id, sku=rm.sku, received_qty="5", accepted_qty="5", uom="UNIT", unit_price=unit_price)
            _db.session.add(grn_line)
            _db.session.flush()
            item = InventoryItem(tenant_id=default_tenant_id, inventory_id=f"INV-CP-{label}-{suffix}", grn_id=grn.id, grn_line_id=grn_line.id, product_id=rm.id, sku=rm.sku, warehouse_id=warehouse.id, status="accepted", kind="lot", quantity="5", uom="UNIT", accepted_qty="5")
            _db.session.add(item)
            _db.session.flush()
            items[label] = item

            from app.services import inventory_ledger
            from app.services.inventory_ledger import LedgerPosting

            inventory_ledger.post(
                LedgerPosting(
                    tenant_id=default_tenant_id,
                    product_id=rm.id,
                    sku=rm.sku,
                    warehouse_id=warehouse.id,
                    quantity="5",
                    uom="UNIT",
                    bucket="available",
                    movement_type="receipt",
                    reference_type="grn",
                    reference_id=f"{grn.id}:{grn_line.id}",
                    unit_cost=unit_price,
                )
            )
        _db.session.commit()

        ids = {"tenant_id": default_tenant_id, "fg_id": fg.id, "rm_id": rm.id, "warehouse_id": warehouse.id, "cheap_item_id": items["cheap"].id, "pricey_item_id": items["pricey"].id}
        yield ids

        from app.models.finished_good_item import FinishedGoodItem
        from app.models.production_consumption import ProductionConsumption
        from app.models.production_run import ProductionRun
        from app.models.stock_balance import StockBalance
        from app.models.stock_ledger import StockLedger

        run_ids = [r.id for r in ProductionRun.query.filter_by(product_id=fg.id).all()]
        if run_ids:
            ProductionConsumption.query.filter(ProductionConsumption.production_run_id.in_(run_ids)).delete(synchronize_session=False)
        FinishedGoodItem.query.filter_by(product_id=fg.id).delete(synchronize_session=False)
        ProductionRun.query.filter_by(product_id=fg.id).delete(synchronize_session=False)
        StockLedger.query.filter(StockLedger.product_id.in_([fg.id, rm.id])).delete(synchronize_session=False)
        StockBalance.query.filter(StockBalance.product_id.in_([fg.id, rm.id])).delete(synchronize_session=False)
        InventoryItem.query.filter(InventoryItem.id.in_([items["cheap"].id, items["pricey"].id])).delete(synchronize_session=False)
        GrnLine.query.filter_by(grn_id=grn.id).delete(synchronize_session=False)
        Grn.query.filter_by(id=grn.id).delete(synchronize_session=False)
        PurchaseOrder.query.filter_by(id=po.id).delete(synchronize_session=False)
        BomComponent.query.filter_by(bom_version_id=version.id).delete(synchronize_session=False)
        BomVersion.query.filter_by(bom_id=bom.id).delete(synchronize_session=False)
        Bom.query.filter_by(id=bom.id).delete(synchronize_session=False)
        Product.query.filter_by(id=fg.id).delete(synchronize_session=False)
        Product.query.filter_by(id=rm.id).delete(synchronize_session=False)
        Warehouse.query.filter_by(id=warehouse.id).delete(synchronize_session=False)
        Party.query.filter_by(id=vendor.id).delete(synchronize_session=False)
        _db.session.commit()


@pytest.fixture
def admin_access(client, fresh_admin):
    resp = client.post("/api/v1/auth/login", json={"email": fresh_admin["email"], "password": fresh_admin["password"]})
    return resp.get_json()["accessToken"]


def test_production_output_is_priced_from_consumed_component_cost(app, client, admin_access, costed_bom):
    """1 UNIT of FG consumes 2 KG of RM @ 50/KG = 100 total -> output unit_cost
    100, and that flows straight through to Finished Goods valuation."""
    headers = {"Authorization": f"Bearer {admin_access}"}
    resp = client.post(
        "/api/v1/inventory/production",
        json={"productId": str(costed_bom["fg_id"]), "quantity": "1", "uom": "UNIT", "warehouseId": str(costed_bom["warehouse_id"])},
        headers=headers,
    )
    assert resp.status_code == 201, resp.get_json()
    run_id = resp.get_json()["id"]

    with app.app_context():
        from app.models.finished_good_item import FinishedGoodItem
        from app.models.production_consumption import ProductionConsumption
        from app.models.stock_ledger import StockLedger
        from app.services import inventory_ledger

        fg_item = FinishedGoodItem.query.filter_by(production_run_id=run_id).one()
        output_posting = StockLedger.query.filter_by(reference_type="production", reference_id=str(fg_item.id), movement_type="production_output").one()
        assert Decimal(output_posting.unit_cost) == Decimal("100")

        consumption = ProductionConsumption.query.filter_by(production_run_id=run_id, is_additional=False).one()
        assert Decimal(consumption.unit_cost) == Decimal("50")
        consume_posting = StockLedger.query.filter_by(reference_type="production", movement_type="production_consume", product_id=costed_bom["rm_id"]).first()
        assert Decimal(consume_posting.unit_cost) == Decimal("50")

        valuation = inventory_ledger.compute_valuation(costed_bom["tenant_id"], warehouse_id=costed_bom["warehouse_id"], bucket="available")
        fg_line = next(l for l in valuation["lines"] if l["productId"] == str(costed_bom["fg_id"]))
        assert Decimal(fg_line["value"]) == Decimal("100.00")
        assert Decimal(fg_line["averageCost"]) == Decimal("100.0000")


def test_production_prices_off_the_actual_picked_inventory_id_not_the_average(app, client, admin_access, costed_bom_with_picked_items):
    """RM has two Inventory IDs: cheap @ 10/unit and pricey @ 100/unit - the
    product-wide weighted average would be 55/unit. Hand-picking 2 units of
    the *cheap* item for the BOM's 2-UNIT requirement must cost the output
    at 2 x 10 = 20, not 2 x 55 = 110."""
    fx = costed_bom_with_picked_items
    headers = {"Authorization": f"Bearer {admin_access}"}
    resp = client.post(
        "/api/v1/inventory/production",
        json={
            "productId": str(fx["fg_id"]),
            "quantity": "1",
            "uom": "UNIT",
            "warehouseId": str(fx["warehouse_id"]),
            "consumedItems": [{"itemId": str(fx["cheap_item_id"]), "productId": str(fx["rm_id"]), "quantity": "2"}],
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.get_json()
    run_id = resp.get_json()["id"]

    with app.app_context():
        from app.models.finished_good_item import FinishedGoodItem
        from app.models.production_consumption import ProductionConsumption
        from app.models.stock_ledger import StockLedger

        consumption = ProductionConsumption.query.filter_by(production_run_id=run_id, is_additional=False).one()
        assert Decimal(consumption.unit_cost) == Decimal("10")

        fg_item = FinishedGoodItem.query.filter_by(production_run_id=run_id).one()
        output_posting = StockLedger.query.filter_by(reference_type="production", reference_id=str(fg_item.id), movement_type="production_output").one()
        assert Decimal(output_posting.unit_cost) == Decimal("20")


def test_production_output_cost_includes_additional_beyond_bom_component(app, client, admin_access, costed_bom):
    """2 KG RM @ 50 (BOM) + 1 KG RM2 @ 20 (additional) = 120 total for 1 UNIT
    output -> unit_cost 120."""
    headers = {"Authorization": f"Bearer {admin_access}"}
    resp = client.post(
        "/api/v1/inventory/production",
        json={
            "productId": str(costed_bom["fg_id"]),
            "quantity": "1",
            "uom": "UNIT",
            "warehouseId": str(costed_bom["warehouse_id"]),
            "additionalComponents": [{"productId": str(costed_bom["rm2_id"]), "quantity": "1", "uom": "KG"}],
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.get_json()
    run_id = resp.get_json()["id"]

    with app.app_context():
        from app.models.finished_good_item import FinishedGoodItem
        from app.models.stock_ledger import StockLedger

        fg_item = FinishedGoodItem.query.filter_by(production_run_id=run_id).one()
        output_posting = StockLedger.query.filter_by(reference_type="production", reference_id=str(fg_item.id), movement_type="production_output").one()
        assert Decimal(output_posting.unit_cost) == Decimal("120")
