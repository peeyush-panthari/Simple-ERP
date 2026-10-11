"""New coverage - a finished good can be bought in (PO -> GRN -> QC pass)
instead of manufactured. Order Allocation only ever picks from
FinishedGoodItem, so grn_post.py::_convert_finished_good_receipts converts
the accepted portion of a finished-good line's InventoryItem into a real
FinishedGoodItem the moment QC passes, draining the source InventoryItem the
same way raw-material consumption already does. This must never post a new
ledger/balance entry - the GRN receipt already posted the real cost/value.

Fixture builds a PO/vendor directly at "issued" status (bypassing the
approve/issue HTTP flow, which is already covered by test_po_state.py) so
the real /grns and /grns/<id>/qc endpoints can be exercised end-to-end -
the same style test_finished_good_items.py uses for production output."""

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from tests.flaskcompat import db as _db


@pytest.fixture
def issued_po(app, default_tenant_id):
    from app.models.location import Location
    from app.models.party import Party
    from app.models.po_line import PoLine
    from app.models.product import Product
    from app.models.purchase_order import PurchaseOrder
    from app.models.warehouse import Warehouse

    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        fg_unit = Product(tenant_id=default_tenant_id, sku=f"TST-FGB-{suffix}", name="FG Bought-in Test (unit)", type="finished_good", uom="UNIT", status="active")
        fg_lot = Product(tenant_id=default_tenant_id, sku=f"TST-FGBL-{suffix}", name="FG Bought-in Test (lot)", type="finished_good", uom="KG", status="active")
        rm = Product(tenant_id=default_tenant_id, sku=f"TST-RMB-{suffix}", name="RM Bought-in Test", type="raw_material", uom="KG", status="active")
        vendor = Party(tenant_id=default_tenant_id, code=f"VEN-{suffix}", legal_name="Test Vendor", display_name="Test Vendor", type="vendor", status="active")
        warehouse = Warehouse(tenant_id=default_tenant_id, code=f"WH-FGB-{suffix}", name="FG Bought-in Test Warehouse", status="active")
        _db.session.add_all([fg_unit, fg_lot, rm, vendor, warehouse])
        _db.session.flush()

        quarantine = Location(tenant_id=default_tenant_id, warehouse_id=warehouse.id, code=f"QTN-{suffix}", type="quarantine", status="active")
        _db.session.add(quarantine)
        _db.session.flush()

        po = PurchaseOrder(
            tenant_id=default_tenant_id, number=f"PO-TST-{suffix}", vendor_id=vendor.id, vendor_name=vendor.display_name,
            warehouse_id=warehouse.id, warehouse_code=warehouse.code, status="issued", expected_date=date.today() + timedelta(days=1),
        )
        _db.session.add(po)
        _db.session.flush()

        lines = {}
        for i, (product, qty) in enumerate([(fg_unit, Decimal("5")), (fg_lot, Decimal("20")), (rm, Decimal("10"))], start=1):
            line = PoLine(tenant_id=default_tenant_id, po_id=po.id, line_no=i, product_id=product.id, sku=product.sku, quantity=qty, uom=product.uom, unit_price=Decimal("100"), tax_code="NA")
            _db.session.add(line)
            _db.session.flush()
            lines[product.sku] = line
        _db.session.commit()

        ids = {
            "tenant_id": default_tenant_id, "po_id": po.id, "warehouse_id": warehouse.id,
            "fg_unit_id": fg_unit.id, "fg_unit_sku": fg_unit.sku, "fg_unit_line_id": lines[fg_unit.sku].id,
            "fg_lot_id": fg_lot.id, "fg_lot_sku": fg_lot.sku, "fg_lot_line_id": lines[fg_lot.sku].id,
            "rm_id": rm.id, "rm_sku": rm.sku, "rm_line_id": lines[rm.sku].id,
        }
        yield ids

        from app.models.finished_good_item import FinishedGoodItem
        from app.models.grn import Grn
        from app.models.grn_line import GrnLine
        from app.models.inventory_item import InventoryItem
        from app.models.stock_balance import StockBalance
        from app.models.stock_ledger import StockLedger

        grn_ids = [g.id for g in Grn.query.filter_by(po_id=po.id).all()]
        for pid in (fg_unit.id, fg_lot.id, rm.id):
            FinishedGoodItem.query.filter_by(product_id=pid).delete(synchronize_session=False)
            InventoryItem.query.filter_by(product_id=pid).delete(synchronize_session=False)
            StockLedger.query.filter_by(product_id=pid).delete(synchronize_session=False)
            StockBalance.query.filter_by(product_id=pid).delete(synchronize_session=False)
        GrnLine.query.filter(GrnLine.grn_id.in_(grn_ids)).delete(synchronize_session=False)
        Grn.query.filter(Grn.id.in_(grn_ids)).delete(synchronize_session=False)
        PoLine.query.filter_by(po_id=po.id).delete(synchronize_session=False)
        PurchaseOrder.query.filter_by(id=po.id).delete(synchronize_session=False)
        Location.query.filter_by(id=quarantine.id).delete(synchronize_session=False)
        Product.query.filter(Product.id.in_([fg_unit.id, fg_lot.id, rm.id])).delete(synchronize_session=False)
        Party.query.filter_by(id=vendor.id).delete(synchronize_session=False)
        Warehouse.query.filter_by(id=warehouse.id).delete(synchronize_session=False)
        _db.session.commit()


@pytest.fixture
def admin_access(client, fresh_admin):
    resp = client.post("/api/v1/auth/login", json={"email": fresh_admin["email"], "password": fresh_admin["password"]})
    return resp.get_json()["accessToken"]


def _create_grn(client, headers, issued_po, lines):
    resp = client.post(
        "/api/v1/grns",
        json={
            "poId": str(issued_po["po_id"]),
            "warehouseId": str(issued_po["warehouse_id"]),
            "invoiceNumber": f"INV-{uuid.uuid4().hex[:10].upper()}",
            "lines": lines,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()


def test_unit_fg_line_qc_pass_converts_inventory_item_to_finished_good_item(app, client, admin_access, issued_po):
    headers = {"Authorization": f"Bearer {admin_access}"}
    grn = _create_grn(client, headers, issued_po, [{"poLineId": str(issued_po["fg_unit_line_id"]), "receivedQty": "5"}])
    fg_line = next(l for l in grn["lines"] if l["sku"] == issued_po["fg_unit_sku"])

    with app.app_context():
        from app.models.inventory_item import InventoryItem
        from app.services import inventory_ledger

        source_items = InventoryItem.query.filter_by(grn_line_id=uuid.UUID(fg_line["id"])).all()
        assert len(source_items) == 5
        assert all(i.kind == "piece" for i in source_items)
        item_ids = [str(i.id) for i in source_items]

        totals_before = inventory_ledger.bucket_totals(issued_po["tenant_id"], issued_po["fg_unit_id"], issued_po["warehouse_id"])

    qc_resp = client.post(
        f"/api/v1/grns/{grn['id']}/qc",
        json={"items": [{"itemId": iid, "decision": "accept"} for iid in item_ids], "lines": []},
        headers=headers,
    )
    assert qc_resp.status_code == 200, qc_resp.get_json()
    assert qc_resp.get_json()["status"] == "posted"

    with app.app_context():
        from app.models.finished_good_item import FinishedGoodItem
        from app.models.inventory_item import InventoryItem
        from app.services import inventory_ledger

        fg_items = FinishedGoodItem.query.filter_by(product_id=issued_po["fg_unit_id"]).all()
        assert len(fg_items) == 5
        assert all(i.kind == "piece" for i in fg_items)
        assert all(i.quantity == Decimal("1") for i in fg_items)
        assert all(i.warehouse_id == issued_po["warehouse_id"] for i in fg_items)
        assert all(i.production_run_id is None for i in fg_items)
        assert {str(i.source_inventory_item_id) for i in fg_items} == set(item_ids)
        assert all(i.inventory_id.startswith("FG-") for i in fg_items)

        drained = InventoryItem.query.filter(InventoryItem.id.in_(item_ids)).all()
        assert all(i.consumed_qty == i.accepted_qty == Decimal("1") for i in drained)

        # Conversion must not double-post: same bucket totals before/after.
        totals_after = inventory_ledger.bucket_totals(issued_po["tenant_id"], issued_po["fg_unit_id"], issued_po["warehouse_id"])
        assert Decimal(totals_after["available"]) == Decimal(totals_before["available"]) + 5


def test_lot_fg_line_partial_accept_only_converts_accepted_portion(app, client, admin_access, issued_po):
    headers = {"Authorization": f"Bearer {admin_access}"}
    grn = _create_grn(client, headers, issued_po, [{"poLineId": str(issued_po["fg_lot_line_id"]), "receivedQty": "20"}])
    fg_line = next(l for l in grn["lines"] if l["sku"] == issued_po["fg_lot_sku"])

    qc_resp = client.post(
        f"/api/v1/grns/{grn['id']}/qc",
        json={"items": [], "lines": [{"lineId": fg_line["id"], "acceptedQty": "15", "rejectedQty": "5", "rejectionCode": "QC-FAIL"}]},
        headers=headers,
    )
    assert qc_resp.status_code == 200, qc_resp.get_json()

    with app.app_context():
        from app.models.finished_good_item import FinishedGoodItem
        from app.models.inventory_item import InventoryItem

        fg_items = FinishedGoodItem.query.filter_by(product_id=issued_po["fg_lot_id"]).all()
        assert len(fg_items) == 1
        assert fg_items[0].kind == "lot"
        assert fg_items[0].quantity == Decimal("15")

        source = InventoryItem.query.filter_by(grn_line_id=uuid.UUID(fg_line["id"])).one()
        assert source.accepted_qty == Decimal("15")
        assert source.rejected_qty == Decimal("5")
        assert source.consumed_qty == Decimal("15")  # only the accepted portion drained


def test_raw_material_qc_pass_is_unaffected(app, client, admin_access, issued_po):
    """Conversion is a no-op when the line's product isn't finished_good."""
    headers = {"Authorization": f"Bearer {admin_access}"}
    grn = _create_grn(client, headers, issued_po, [{"poLineId": str(issued_po["rm_line_id"]), "receivedQty": "10"}])
    rm_line = next(l for l in grn["lines"] if l["sku"] == issued_po["rm_sku"])

    qc_resp = client.post(
        f"/api/v1/grns/{grn['id']}/qc",
        json={"items": [], "lines": [{"lineId": rm_line["id"], "acceptedQty": "10", "rejectedQty": "0"}]},
        headers=headers,
    )
    assert qc_resp.status_code == 200, qc_resp.get_json()

    with app.app_context():
        from app.models.finished_good_item import FinishedGoodItem
        from app.models.inventory_item import InventoryItem

        assert FinishedGoodItem.query.filter_by(product_id=issued_po["rm_id"]).count() == 0
        source = InventoryItem.query.filter_by(grn_line_id=uuid.UUID(rm_line["id"])).one()
        assert source.accepted_qty == Decimal("10")
        assert source.consumed_qty == Decimal("0")  # raw material drains via production consumption, not this path


def _stranded_items(tenant_id, product_id):
    """Mirrors scripts/backfill_fg_grn_conversion.py::_stranded_items, scoped
    to one product so the test stays isolated from other fixtures' rows."""
    from app.models.inventory_item import InventoryItem

    return InventoryItem.query.filter(
        InventoryItem.tenant_id == tenant_id,
        InventoryItem.product_id == product_id,
        InventoryItem.accepted_qty > InventoryItem.consumed_qty,
        InventoryItem.deleted_at.is_(None),
    ).all()


def test_backfill_converts_stranded_items_and_is_idempotent(app, client, admin_access, issued_po):
    """Simulates pre-fix stranded data: an InventoryItem already accepted (as
    if converted before this feature existed) with consumed_qty still 0."""
    headers = {"Authorization": f"Bearer {admin_access}"}
    grn = _create_grn(client, headers, issued_po, [{"poLineId": str(issued_po["fg_unit_line_id"]), "receivedQty": "2"}])
    fg_line = next(l for l in grn["lines"] if l["sku"] == issued_po["fg_unit_sku"])

    with app.app_context():
        from app.models.grn import Grn
        from app.models.inventory_item import InventoryItem
        from app.services.grn_post import _convert_inventory_item_to_finished_good

        # Roll the GRN back to look pre-conversion: items accepted, but
        # never drained (as if received before this feature shipped).
        items = InventoryItem.query.filter_by(grn_line_id=uuid.UUID(fg_line["id"])).all()
        for item in items:
            item.status = "accepted"
            item.accepted_qty = 1
            item.consumed_qty = 0
        Grn.query.filter_by(id=uuid.UUID(grn["id"])).update({"status": "posted"})
        _db.session.commit()

        stranded = _stranded_items(issued_po["tenant_id"], issued_po["fg_unit_id"])
        assert len(stranded) == 2

        for item in stranded:
            _convert_inventory_item_to_finished_good(item)
        _db.session.commit()

        assert _stranded_items(issued_po["tenant_id"], issued_po["fg_unit_id"]) == []  # idempotent - nothing left on a second pass

        from app.models.finished_good_item import FinishedGoodItem

        assert FinishedGoodItem.query.filter_by(product_id=issued_po["fg_unit_id"]).count() == 2
