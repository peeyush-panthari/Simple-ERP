"""New coverage - manual Finished Good Allocation: POST /orders/<id>/
allocate-items and DELETE /orders/allocations/<id>. The operator picks
specific FinishedGoodItem(s) for one order line, unlike POST /orders/<id>/
allocate which lets FEFO/FIFO pick a batch by quantity alone. Verifies the
same order/line bookkeeping that automatic allocation already does, plus
the new item-level claim tracking (FinishedGoodItem.allocated_qty,
FinishedGoodAllocation rows) and that removing an allocation reverses all
of it precisely."""

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from tests.flaskcompat import db as _db


@pytest.fixture
def order_with_fg_items(app, default_tenant_id):
    from app.models.bom import Bom
    from app.models.bom_version import BomVersion
    from app.models.order import Order
    from app.models.order_line import OrderLine
    from app.models.party import Party
    from app.models.product import Product
    from app.models.warehouse import Warehouse

    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        fg = Product(tenant_id=default_tenant_id, sku=f"TST-FGA-{suffix}", name="FG Allocation Test", type="finished_good", uom="UNIT", status="active")
        warehouse = Warehouse(tenant_id=default_tenant_id, code=f"WH-FGA-{suffix}", name="FG Allocation Test Warehouse", status="active")
        customer = Party(tenant_id=default_tenant_id, code=f"CUST-{suffix}", legal_name="Test Customer Ltd", display_name="Test Customer", type="customer", status="active")
        _db.session.add_all([fg, warehouse, customer])
        _db.session.flush()

        bom = Bom(tenant_id=default_tenant_id, product_id=fg.id, product_sku=fg.sku, status="active")
        _db.session.add(bom)
        _db.session.flush()
        version = BomVersion(tenant_id=default_tenant_id, bom_id=bom.id, version=1, state="approved", yield_percent=100, effective_from=date.today() - timedelta(days=1))
        _db.session.add(version)

        order = Order(tenant_id=default_tenant_id, number=f"SO-FGA-{suffix}", customer_id=customer.id, customer_name=customer.display_name, status="confirmed", promised_date=date.today() + timedelta(days=7), warehouse_id=warehouse.id, total="200")
        _db.session.add(order)
        _db.session.flush()
        line = OrderLine(tenant_id=default_tenant_id, order_id=order.id, line_no=1, product_id=fg.id, sku=fg.sku, quantity="2", uom="UNIT", unit_price="100", tax_code="NONE", gross_amount="200", net_amount="200", status="open")
        _db.session.add(line)
        _db.session.commit()

        ids = {"tenant_id": default_tenant_id, "fg_id": fg.id, "warehouse_id": warehouse.id, "order_id": order.id, "line_id": line.id, "order_number": order.number, "sku": fg.sku}
        yield ids

        from app.models.finished_good_allocation import FinishedGoodAllocation
        from app.models.finished_good_item import FinishedGoodItem
        from app.models.production_run import ProductionRun
        from app.models.reservation import Reservation
        from app.models.stock_balance import StockBalance
        from app.models.stock_ledger import StockLedger

        fg_item_ids = [i.id for i in FinishedGoodItem.query.filter_by(product_id=fg.id).all()]
        reservation_ids = [r.id for r in Reservation.query.filter_by(order_id=order.id).all()]
        if reservation_ids:
            FinishedGoodAllocation.query.filter(FinishedGoodAllocation.reservation_id.in_(reservation_ids)).delete(synchronize_session=False)
            Reservation.query.filter(Reservation.id.in_(reservation_ids)).delete(synchronize_session=False)
        FinishedGoodItem.query.filter_by(product_id=fg.id).delete(synchronize_session=False)
        OrderLine.query.filter_by(order_id=order.id).delete(synchronize_session=False)
        Order.query.filter_by(id=order.id).delete(synchronize_session=False)
        StockLedger.query.filter_by(product_id=fg.id).delete(synchronize_session=False)
        StockBalance.query.filter_by(product_id=fg.id).delete(synchronize_session=False)
        ProductionRun.query.filter_by(product_id=fg.id).delete(synchronize_session=False)
        BomVersion.query.filter_by(bom_id=bom.id).delete(synchronize_session=False)
        Bom.query.filter_by(id=bom.id).delete(synchronize_session=False)
        Product.query.filter_by(id=fg.id).delete(synchronize_session=False)
        Warehouse.query.filter_by(id=warehouse.id).delete(synchronize_session=False)
        Party.query.filter_by(id=customer.id).delete(synchronize_session=False)
        _db.session.commit()


@pytest.fixture
def order_with_lot_fg_item(app, default_tenant_id):
    """Same shape as order_with_fg_items, but a KG-tracked (kind='lot')
    product - the only case where allocating LESS than a FinishedGoodItem's
    full quantity is possible, so status can land on 'partially_reserved'
    rather than jumping straight to 'reserved'."""
    from app.models.bom import Bom
    from app.models.bom_version import BomVersion
    from app.models.order import Order
    from app.models.order_line import OrderLine
    from app.models.party import Party
    from app.models.product import Product
    from app.models.warehouse import Warehouse

    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        fg = Product(tenant_id=default_tenant_id, sku=f"TST-FGL-{suffix}", name="FG Lot Allocation Test", type="finished_good", uom="KG", status="active")
        warehouse = Warehouse(tenant_id=default_tenant_id, code=f"WH-FGL-{suffix}", name="FG Lot Allocation Test Warehouse", status="active")
        customer = Party(tenant_id=default_tenant_id, code=f"CUST-L-{suffix}", legal_name="Test Customer Ltd", display_name="Test Customer", type="customer", status="active")
        _db.session.add_all([fg, warehouse, customer])
        _db.session.flush()

        bom = Bom(tenant_id=default_tenant_id, product_id=fg.id, product_sku=fg.sku, status="active")
        _db.session.add(bom)
        _db.session.flush()
        version = BomVersion(tenant_id=default_tenant_id, bom_id=bom.id, version=1, state="approved", yield_percent=100, effective_from=date.today() - timedelta(days=1))
        _db.session.add(version)

        order = Order(tenant_id=default_tenant_id, number=f"SO-FGL-{suffix}", customer_id=customer.id, customer_name=customer.display_name, status="confirmed", promised_date=date.today() + timedelta(days=7), warehouse_id=warehouse.id, total="1000")
        _db.session.add(order)
        _db.session.flush()
        line = OrderLine(tenant_id=default_tenant_id, order_id=order.id, line_no=1, product_id=fg.id, sku=fg.sku, quantity="10", uom="KG", unit_price="100", tax_code="NONE", gross_amount="1000", net_amount="1000", status="open")
        _db.session.add(line)
        _db.session.commit()

        ids = {"tenant_id": default_tenant_id, "fg_id": fg.id, "warehouse_id": warehouse.id, "order_id": order.id, "line_id": line.id, "order_number": order.number, "sku": fg.sku}
        yield ids

        from app.models.finished_good_allocation import FinishedGoodAllocation
        from app.models.finished_good_item import FinishedGoodItem
        from app.models.production_run import ProductionRun
        from app.models.reservation import Reservation
        from app.models.stock_balance import StockBalance
        from app.models.stock_ledger import StockLedger

        reservation_ids = [r.id for r in Reservation.query.filter_by(order_id=order.id).all()]
        if reservation_ids:
            FinishedGoodAllocation.query.filter(FinishedGoodAllocation.reservation_id.in_(reservation_ids)).delete(synchronize_session=False)
            Reservation.query.filter(Reservation.id.in_(reservation_ids)).delete(synchronize_session=False)
        FinishedGoodItem.query.filter_by(product_id=fg.id).delete(synchronize_session=False)
        OrderLine.query.filter_by(order_id=order.id).delete(synchronize_session=False)
        Order.query.filter_by(id=order.id).delete(synchronize_session=False)
        StockLedger.query.filter_by(product_id=fg.id).delete(synchronize_session=False)
        StockBalance.query.filter_by(product_id=fg.id).delete(synchronize_session=False)
        ProductionRun.query.filter_by(product_id=fg.id).delete(synchronize_session=False)
        BomVersion.query.filter_by(bom_id=bom.id).delete(synchronize_session=False)
        Bom.query.filter_by(id=bom.id).delete(synchronize_session=False)
        Product.query.filter_by(id=fg.id).delete(synchronize_session=False)
        Warehouse.query.filter_by(id=warehouse.id).delete(synchronize_session=False)
        Party.query.filter_by(id=customer.id).delete(synchronize_session=False)
        _db.session.commit()


@pytest.fixture
def admin_access(client, fresh_admin):
    resp = client.post("/api/v1/auth/login", json={"email": fresh_admin["email"], "password": fresh_admin["password"]})
    return resp.get_json()["accessToken"]


def _post_units(app, client, headers, ctx, qty):
    resp = client.post("/api/v1/inventory/production", json={"productId": str(ctx["fg_id"]), "quantity": str(qty), "uom": "UNIT", "warehouseId": str(ctx["warehouse_id"])}, headers=headers)
    assert resp.status_code == 201, resp.get_json()
    with app.app_context():
        from app.models.finished_good_item import FinishedGoodItem

        return [str(i.id) for i in FinishedGoodItem.query.filter_by(product_id=ctx["fg_id"]).order_by(FinishedGoodItem.inventory_id).all()]


def _post_lot(app, client, headers, ctx, qty):
    resp = client.post("/api/v1/inventory/production", json={"productId": str(ctx["fg_id"]), "quantity": str(qty), "uom": "KG", "warehouseId": str(ctx["warehouse_id"])}, headers=headers)
    assert resp.status_code == 201, resp.get_json()
    with app.app_context():
        from app.models.finished_good_item import FinishedGoodItem

        return str(FinishedGoodItem.query.filter_by(product_id=ctx["fg_id"]).first().id)


def test_allocate_items_fully_covers_line_and_reversal_restores_everything(app, client, admin_access, order_with_fg_items):
    ctx = order_with_fg_items
    headers = {"Authorization": f"Bearer {admin_access}"}
    item_ids = _post_units(app, client, headers, ctx, 2)

    resp = client.post(
        f"/api/v1/orders/{ctx['order_id']}/allocate-items",
        json={"orderLineId": str(ctx["line_id"]), "items": [{"itemId": item_ids[0], "quantity": "1"}, {"itemId": item_ids[1], "quantity": "1"}]},
        headers=headers,
    )
    assert resp.status_code == 200, resp.get_json()
    order_data = resp.get_json()
    assert order_data["status"] == "allocated"
    line_data = next(l for l in order_data["lines"] if l["id"] == str(ctx["line_id"]))
    assert line_data["status"] == "allocated"
    assert Decimal(line_data["allocatedQty"]) == Decimal("2")

    with app.app_context():
        from app.models.finished_good_allocation import FinishedGoodAllocation
        from app.models.finished_good_item import FinishedGoodItem
        from app.models.reservation import Reservation
        from app.services import inventory_ledger

        items = FinishedGoodItem.query.filter(FinishedGoodItem.id.in_(item_ids)).all()
        assert all(i.allocated_qty == Decimal("1") for i in items)
        assert all(i.status == "reserved" for i in items)
        assert all(str(i.allocated_order_id) == str(ctx["order_id"]) for i in items)
        reservation = Reservation.query.filter_by(order_id=ctx["order_id"]).first()
        assert reservation is not None
        assert reservation.status == "open"
        assert Decimal(reservation.quantity) == Decimal("2")
        allocations = FinishedGoodAllocation.query.filter_by(reservation_id=reservation.id).all()
        assert len(allocations) == 2
        allocation_ids = [str(a.id) for a in allocations]

        # The allocated stock physically moved out of `available` into
        # `reserved` - not just subtracted at read time.
        totals = inventory_ledger.bucket_totals(ctx["tenant_id"], ctx["fg_id"], ctx["warehouse_id"])
        assert totals["available"] == "0.000000"
        assert totals["reserved"] == "2.000000"

    list_resp = client.get(f"/api/v1/orders/lines/{ctx['line_id']}/allocations", headers=headers)
    assert list_resp.status_code == 200
    rows = list_resp.get_json()
    assert len(rows) == 2
    assert {r["allocationId"] for r in rows} == set(allocation_ids)
    assert all(r["inventoryId"] and r["inventoryId"].startswith("FG-") for r in rows)

    # Remove one allocation - line drops out of 'allocated', order drops to
    # 'partially_allocated', that one item frees back up, the other stays put.
    del_resp = client.delete(f"/api/v1/orders/allocations/{allocation_ids[0]}", headers=headers)
    assert del_resp.status_code == 200, del_resp.get_json()
    assert del_resp.get_json()["status"] == "partially_allocated"

    with app.app_context():
        from app.models.finished_good_item import FinishedGoodItem
        from app.models.order_line import OrderLine
        from app.models.reservation import Reservation
        from app.services import inventory_ledger

        line = OrderLine.query.filter_by(id=ctx["line_id"]).first()
        assert line.status == "open"
        assert Decimal(line.allocated_qty) == Decimal("1")
        reservation = Reservation.query.filter_by(order_id=ctx["order_id"], status="open").first()
        assert Decimal(reservation.quantity) == Decimal("1")
        items = FinishedGoodItem.query.filter(FinishedGoodItem.id.in_(item_ids)).all()
        freed = [i for i in items if i.allocated_qty == Decimal("0")]
        assert len(freed) == 1
        assert freed[0].allocated_order_id is None
        assert freed[0].status == "available"

        totals = inventory_ledger.bucket_totals(ctx["tenant_id"], ctx["fg_id"], ctx["warehouse_id"])
        assert totals["available"] == "1.000000"
        assert totals["reserved"] == "1.000000"

    # Remove the last allocation - reservation fully releases, line link clears.
    del_resp2 = client.delete(f"/api/v1/orders/allocations/{allocation_ids[1]}", headers=headers)
    assert del_resp2.status_code == 200, del_resp2.get_json()
    assert del_resp2.get_json()["status"] == "confirmed"

    with app.app_context():
        from app.models.order_line import OrderLine
        from app.models.reservation import Reservation
        from app.services import inventory_ledger

        line = OrderLine.query.filter_by(id=ctx["line_id"]).first()
        assert line.reservation_id is None
        assert Decimal(line.allocated_qty) == Decimal("0")
        reservation = Reservation.query.filter_by(order_id=ctx["order_id"]).first()
        assert reservation.status == "released"

        totals = inventory_ledger.bucket_totals(ctx["tenant_id"], ctx["fg_id"], ctx["warehouse_id"])
        assert totals["available"] == "2.000000"
        assert totals["reserved"] == "0.000000"


def test_allocate_items_rejects_non_finished_good_item(app, client, admin_access, order_with_fg_items):
    ctx = order_with_fg_items
    headers = {"Authorization": f"Bearer {admin_access}"}
    resp = client.post(
        f"/api/v1/orders/{ctx['order_id']}/allocate-items",
        json={"orderLineId": str(ctx["line_id"]), "items": [{"itemId": str(uuid.uuid4()), "quantity": "1"}]},
        headers=headers,
    )
    assert resp.status_code == 422
    assert resp.get_json()["code"] == "ALLOCATION_INVALID"


def test_allocate_items_rejects_exceeding_line_quantity(app, client, admin_access, order_with_fg_items):
    ctx = order_with_fg_items
    headers = {"Authorization": f"Bearer {admin_access}"}
    item_ids = _post_units(app, client, headers, ctx, 5)

    resp = client.post(
        f"/api/v1/orders/{ctx['order_id']}/allocate-items",
        json={"orderLineId": str(ctx["line_id"]), "items": [{"itemId": iid, "quantity": "1"} for iid in item_ids]},
        headers=headers,
    )
    assert resp.status_code == 422
    assert resp.get_json()["code"] == "ALLOCATION_EXCEEDS_LINE"


def test_shipping_releases_manually_allocated_items_from_reserved(app, client, admin_access, order_with_fg_items):
    """The gap this whole change had to close: ship_order used to never
    touch FinishedGoodItem at all - a manually-picked item's allocated_qty/
    status would be orphaned forever after shipment. Now issue_reservation
    walks FinishedGoodAllocation and reconciles each item, and debits the
    `reserved` bucket (not `available` - the goods already left it)."""
    ctx = order_with_fg_items
    headers = {"Authorization": f"Bearer {admin_access}"}
    item_ids = _post_units(app, client, headers, ctx, 2)

    resp = client.post(
        f"/api/v1/orders/{ctx['order_id']}/allocate-items",
        json={"orderLineId": str(ctx["line_id"]), "items": [{"itemId": item_ids[0], "quantity": "1"}, {"itemId": item_ids[1], "quantity": "1"}]},
        headers=headers,
    )
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["status"] == "allocated"

    pack_resp = client.post(f"/api/v1/orders/{ctx['order_id']}/pack", headers=headers)
    assert pack_resp.status_code == 200, pack_resp.get_json()

    ship_resp = client.post(f"/api/v1/orders/{ctx['order_id']}/ship", headers=headers)
    assert ship_resp.status_code == 200, ship_resp.get_json()
    order_data = ship_resp.get_json()
    assert order_data["status"] == "shipped"
    line_data = next(l for l in order_data["lines"] if l["id"] == str(ctx["line_id"]))
    assert line_data["status"] == "shipped"

    with app.app_context():
        from app.models.finished_good_item import FinishedGoodItem
        from app.models.reservation import Reservation
        from app.services import inventory_ledger

        items = FinishedGoodItem.query.filter(FinishedGoodItem.id.in_(item_ids)).all()
        assert all(i.status == "shipped" for i in items)
        assert all(i.shipped_qty == Decimal("1") for i in items)
        assert all(i.allocated_qty == Decimal("0") for i in items)

        reservation = Reservation.query.filter_by(order_id=ctx["order_id"]).first()
        assert reservation.status == "issued"

        # The goods left `reserved` entirely - not posted back to `available`.
        totals = inventory_ledger.bucket_totals(ctx["tenant_id"], ctx["fg_id"], ctx["warehouse_id"])
        assert totals["available"] == "0.000000"
        assert totals["reserved"] == "0.000000"


def test_transfer_and_status_change_blocked_while_allocated(app, client, admin_access, order_with_fg_items):
    ctx = order_with_fg_items
    headers = {"Authorization": f"Bearer {admin_access}"}
    item_ids = _post_units(app, client, headers, ctx, 1)

    resp = client.post(
        f"/api/v1/orders/{ctx['order_id']}/allocate-items",
        json={"orderLineId": str(ctx["line_id"]), "items": [{"itemId": item_ids[0], "quantity": "1"}]},
        headers=headers,
    )
    assert resp.status_code == 200, resp.get_json()

    with app.app_context():
        from app.models.warehouse import Warehouse

        other_warehouse = Warehouse(tenant_id=ctx["tenant_id"], code=f"WH-OTHER-{uuid.uuid4().hex[:8]}", name="Other Warehouse", status="active")
        _db.session.add(other_warehouse)
        _db.session.commit()
        other_warehouse_id = str(other_warehouse.id)

    transfer_resp = client.post(f"/api/v1/inventory/finished-goods/{item_ids[0]}/transfer", json={"toWarehouseId": other_warehouse_id}, headers=headers)
    assert transfer_resp.status_code == 422
    assert transfer_resp.get_json()["code"] == "FG_ITEM_ALLOCATED"

    status_resp = client.post(f"/api/v1/inventory/finished-goods/{item_ids[0]}/status", json={"toStatus": "quarantine"}, headers=headers)
    assert status_resp.status_code == 422
    assert status_resp.get_json()["code"] == "FG_ITEM_ALLOCATED"

    with app.app_context():
        from app.models.warehouse import Warehouse

        Warehouse.query.filter_by(id=other_warehouse_id).delete(synchronize_session=False)
        _db.session.commit()


def test_cancel_order_releases_manually_picked_reservation(app, client, admin_access, order_with_fg_items):
    ctx = order_with_fg_items
    headers = {"Authorization": f"Bearer {admin_access}"}
    item_ids = _post_units(app, client, headers, ctx, 2)

    resp = client.post(
        f"/api/v1/orders/{ctx['order_id']}/allocate-items",
        json={"orderLineId": str(ctx["line_id"]), "items": [{"itemId": iid, "quantity": "1"} for iid in item_ids]},
        headers=headers,
    )
    assert resp.status_code == 200, resp.get_json()

    with app.app_context():
        # order_with_fg_items builds the Order directly (not through
        # _create_order), so it never applied credit usage the way a real
        # order does - cancel_order always releases order.total, so credit
        # has to be applied first or the release would drive it negative.
        from app.models.order import Order
        from app.services.party_repo import apply_credit_usage_for_party

        order = Order.query.filter_by(id=ctx["order_id"]).first()
        apply_credit_usage_for_party(ctx["tenant_id"], order.customer_id, delta=str(order.total), reference=f"{order.number} setup", allow_override=True)
        _db.session.commit()

    cancel_resp = client.post(f"/api/v1/orders/{ctx['order_id']}/cancel", json={"reason": "Customer changed their mind"}, headers=headers)
    assert cancel_resp.status_code == 200, cancel_resp.get_json()

    with app.app_context():
        from app.models.finished_good_item import FinishedGoodItem
        from app.models.reservation import Reservation
        from app.services import inventory_ledger

        items = FinishedGoodItem.query.filter(FinishedGoodItem.id.in_(item_ids)).all()
        assert all(i.status == "available" for i in items)
        assert all(i.allocated_qty == Decimal("0") for i in items)
        reservation = Reservation.query.filter_by(order_id=ctx["order_id"]).first()
        assert reservation.status == "released"

        totals = inventory_ledger.bucket_totals(ctx["tenant_id"], ctx["fg_id"], ctx["warehouse_id"])
        assert totals["available"] == "2.000000"
        assert totals["reserved"] == "0.000000"


def test_automatic_allocation_moves_stock_to_reserved_bucket_and_ship_clears_it(app, client, admin_access, order_with_fg_items):
    """POST /orders/:id/allocate - the automatic FEFO/FIFO path, which has
    zero frontend UI today - had zero test coverage of the bucket math it
    now performs. Confirms it stays consistent with the manual path: reserve
    moves available->reserved, ship debits reserved (not available)."""
    ctx = order_with_fg_items
    headers = {"Authorization": f"Bearer {admin_access}"}
    _post_units(app, client, headers, ctx, 2)

    resp = client.post(f"/api/v1/orders/{ctx['order_id']}/allocate", json={"warehouseId": str(ctx["warehouse_id"])}, headers=headers)
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["status"] == "allocated"

    with app.app_context():
        from app.services import inventory_ledger

        totals = inventory_ledger.bucket_totals(ctx["tenant_id"], ctx["fg_id"], ctx["warehouse_id"])
        assert totals["available"] == "0.000000"
        assert totals["reserved"] == "2.000000"

    pack_resp = client.post(f"/api/v1/orders/{ctx['order_id']}/pack", headers=headers)
    assert pack_resp.status_code == 200, pack_resp.get_json()

    ship_resp = client.post(f"/api/v1/orders/{ctx['order_id']}/ship", headers=headers)
    assert ship_resp.status_code == 200, ship_resp.get_json()
    assert ship_resp.get_json()["status"] == "shipped"

    with app.app_context():
        from app.services import inventory_ledger

        totals = inventory_ledger.bucket_totals(ctx["tenant_id"], ctx["fg_id"], ctx["warehouse_id"])
        assert totals["available"] == "0.000000"
        assert totals["reserved"] == "0.000000"


def test_partial_lot_allocation_status_and_reallocation(app, client, admin_access, order_with_lot_fg_item):
    """UNIT-kind items are always all-or-nothing (quantity=1), so only a
    lot-kind item can show 'partially_reserved' - and it must still accept
    a second allocate-items call topping up the remainder later."""
    ctx = order_with_lot_fg_item
    headers = {"Authorization": f"Bearer {admin_access}"}
    item_id = _post_lot(app, client, headers, ctx, 10)

    resp = client.post(
        f"/api/v1/orders/{ctx['order_id']}/allocate-items",
        json={"orderLineId": str(ctx["line_id"]), "items": [{"itemId": item_id, "quantity": "4"}]},
        headers=headers,
    )
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["status"] == "partially_allocated"

    with app.app_context():
        from app.models.finished_good_item import FinishedGoodItem
        from app.services import inventory_ledger

        item = FinishedGoodItem.query.filter_by(id=item_id).first()
        assert item.status == "partially_reserved"
        assert item.allocated_qty == Decimal("4")

        totals = inventory_ledger.bucket_totals(ctx["tenant_id"], ctx["fg_id"], ctx["warehouse_id"])
        assert totals["available"] == "6.000000"
        assert totals["reserved"] == "4.000000"

    # Top up the same item with its remaining free quantity - status should
    # not still be blocked by having been 'partially_reserved' already.
    resp2 = client.post(
        f"/api/v1/orders/{ctx['order_id']}/allocate-items",
        json={"orderLineId": str(ctx["line_id"]), "items": [{"itemId": item_id, "quantity": "6"}]},
        headers=headers,
    )
    assert resp2.status_code == 200, resp2.get_json()
    assert resp2.get_json()["status"] == "allocated"

    with app.app_context():
        from app.models.finished_good_item import FinishedGoodItem
        from app.services import inventory_ledger

        item = FinishedGoodItem.query.filter_by(id=item_id).first()
        assert item.status == "reserved"
        assert item.allocated_qty == Decimal("10")

        totals = inventory_ledger.bucket_totals(ctx["tenant_id"], ctx["fg_id"], ctx["warehouse_id"])
        assert totals["available"] == "0.000000"
        assert totals["reserved"] == "10.000000"


def test_reservation_warehouse_comes_from_the_picked_item_not_the_order(app, client, admin_access, order_with_fg_items):
    """Orders carry no warehouse of their own any more - regression test for
    the bug this uncovered: allocate-items used to stamp the new
    Reservation's warehouse_id from order.warehouse_id, which could silently
    disagree with the actual FinishedGoodItem(s) picked. Blank out the
    order's (now-legacy, nullable) warehouse_id entirely before allocating,
    to prove the reservation's warehouse is derived purely from the item."""
    ctx = order_with_fg_items
    headers = {"Authorization": f"Bearer {admin_access}"}
    item_ids = _post_units(app, client, headers, ctx, 1)

    with app.app_context():
        from app.models.order import Order

        Order.query.filter_by(id=ctx["order_id"]).update({"warehouse_id": None})
        _db.session.commit()

    resp = client.post(
        f"/api/v1/orders/{ctx['order_id']}/allocate-items",
        json={"orderLineId": str(ctx["line_id"]), "items": [{"itemId": item_ids[0], "quantity": "1"}]},
        headers=headers,
    )
    assert resp.status_code == 200, resp.get_json()

    with app.app_context():
        from app.models.finished_good_item import FinishedGoodItem
        from app.models.reservation import Reservation

        item = FinishedGoodItem.query.filter_by(id=item_ids[0]).first()
        reservation = Reservation.query.filter_by(order_id=ctx["order_id"]).first()
        assert reservation is not None
        assert str(reservation.warehouse_id) == str(item.warehouse_id) == str(ctx["warehouse_id"])


def test_allocate_items_rejects_a_mixed_warehouse_pick(app, client, admin_access, order_with_fg_items):
    """The second item is inserted directly (not via POST /inventory/
    production) - that route works fine on its own, but issuing it against a
    second warehouse immediately before allocate-items locks both items in
    the same transaction was observed to leave the production request's
    connection idle-in-transaction, deadlocking this test's own cleanup
    against a lock that connection never released. Sidestepping the HTTP
    round-trip for test-data setup avoids that without masking what this
    test actually verifies: allocate-items itself rejects a mixed-warehouse
    pick."""
    ctx = order_with_fg_items
    headers = {"Authorization": f"Bearer {admin_access}"}
    item_ids = _post_units(app, client, headers, ctx, 1)

    with app.app_context():
        from app.models.finished_good_item import FinishedGoodItem
        from app.models.warehouse import Warehouse

        first_item = FinishedGoodItem.query.filter_by(id=item_ids[0]).first()
        other_warehouse = Warehouse(tenant_id=ctx["tenant_id"], code=f"WH-OTHER-{uuid.uuid4().hex[:8]}", name="Other Warehouse", status="active")
        _db.session.add(other_warehouse)
        _db.session.flush()
        other_item = FinishedGoodItem(
            tenant_id=ctx["tenant_id"],
            inventory_id=f"FG-TEST-{uuid.uuid4().hex[:8]}",
            production_run_id=first_item.production_run_id,
            product_id=ctx["fg_id"],
            sku=ctx["sku"],
            warehouse_id=other_warehouse.id,
            status="available",
            kind="piece",
            quantity="1",
            uom="UNIT",
        )
        _db.session.add(other_item)
        _db.session.commit()
        other_warehouse_id = str(other_warehouse.id)
        other_item_id = str(other_item.id)

    resp = client.post(
        f"/api/v1/orders/{ctx['order_id']}/allocate-items",
        json={"orderLineId": str(ctx["line_id"]), "items": [{"itemId": item_ids[0], "quantity": "1"}, {"itemId": other_item_id, "quantity": "1"}]},
        headers=headers,
    )
    assert resp.status_code == 422, resp.get_json()
    assert resp.get_json()["code"] == "ALLOCATION_MULTIPLE_WAREHOUSES"

    with app.app_context():
        from app.models.finished_good_item import FinishedGoodItem
        from app.models.warehouse import Warehouse

        FinishedGoodItem.query.filter_by(id=other_item_id).delete(synchronize_session=False)
        Warehouse.query.filter_by(id=other_warehouse_id).delete(synchronize_session=False)
        _db.session.commit()
