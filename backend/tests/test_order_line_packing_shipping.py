"""Order Shipping tab's per-line pack/ship workflow - POST /orders/lines/
<id>/pack and /orders/lines/<id>/ship. Both take a quantity (which may be
less than what's outstanding, landing the line on "partially packed"/
"partially shipped" rather than fully done) instead of acting on a whole
order at once like the legacy POST /orders/<id>/pack and /:id/ship still do.
Packing is pure tracking (no stock movement); shipping is a real partial
issue against the line's reservation - see issue_reservation_partial in
inventory_ledger.py. Reuses test_order_packing.py's order_with_fg_items
fixture pattern (a 2-unit line, manually picked so there are two real
FinishedGoodItem inventory IDs to allocate/ship)."""

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
        fg = Product(tenant_id=default_tenant_id, sku=f"TST-SHIP-{suffix}", name="Order Line Shipping Test FG", type="finished_good", uom="UNIT", status="active")
        warehouse = Warehouse(tenant_id=default_tenant_id, code=f"WH-SHIP-{suffix}", name="Order Line Shipping Test Warehouse", status="active")
        customer = Party(tenant_id=default_tenant_id, code=f"CUST-SHIP-{suffix}", legal_name="Test Customer Ltd", display_name="Test Customer", type="customer", status="active")
        _db.session.add_all([fg, warehouse, customer])
        _db.session.flush()

        bom = Bom(tenant_id=default_tenant_id, product_id=fg.id, product_sku=fg.sku, status="active")
        _db.session.add(bom)
        _db.session.flush()
        version = BomVersion(tenant_id=default_tenant_id, bom_id=bom.id, version=1, state="approved", yield_percent=100, effective_from=date.today() - timedelta(days=1))
        _db.session.add(version)

        order = Order(tenant_id=default_tenant_id, number=f"SO-SHIP-{suffix}", customer_id=customer.id, customer_name=customer.display_name, status="confirmed", promised_date=date.today() + timedelta(days=7), warehouse_id=warehouse.id, total="200")
        _db.session.add(order)
        _db.session.flush()
        line = OrderLine(tenant_id=default_tenant_id, order_id=order.id, line_no=1, product_id=fg.id, sku=fg.sku, quantity="2", uom="UNIT", unit_price="100", tax_code="NONE", gross_amount="200", net_amount="200", status="open")
        _db.session.add(line)
        _db.session.commit()

        ids = {"tenant_id": default_tenant_id, "fg_id": fg.id, "warehouse_id": warehouse.id, "order_id": order.id, "line_id": line.id}
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


def _allocate(app, client, headers, ctx) -> list[str]:
    """Produces 2 real FinishedGoodItems and manually picks both onto the
    order line, so the line ends up allocated_qty=2 with two real
    inventory IDs (not just a FEFO batch reservation) - what the Order
    Shipping tab's Inventory ID column and per-item ship reconciliation
    need to be exercised for real."""
    resp = client.post("/api/v1/inventory/production", json={"productId": str(ctx["fg_id"]), "quantity": "2", "uom": "UNIT", "warehouseId": str(ctx["warehouse_id"])}, headers=headers)
    assert resp.status_code == 201, resp.get_json()
    with app.app_context():
        from app.models.finished_good_item import FinishedGoodItem

        item_ids = [str(i.id) for i in FinishedGoodItem.query.filter_by(product_id=ctx["fg_id"]).order_by(FinishedGoodItem.inventory_id).all()]

    alloc_resp = client.post(
        f"/api/v1/orders/{ctx['order_id']}/allocate-items",
        json={"orderLineId": str(ctx["line_id"]), "items": [{"itemId": item_ids[0], "quantity": "1"}, {"itemId": item_ids[1], "quantity": "1"}]},
        headers=headers,
    )
    assert alloc_resp.status_code == 200, alloc_resp.get_json()
    assert alloc_resp.get_json()["status"] == "allocated"
    return item_ids


def _reserved_balance(tenant_id, product_id) -> Decimal:
    from app.models.stock_balance import StockBalance
    from app.core.money import to_decimal

    rows = StockBalance.query.filter_by(tenant_id=tenant_id, product_id=product_id, bucket="reserved").all()
    return sum((to_decimal(r.quantity) for r in rows), Decimal("0"))


def test_get_order_lists_real_inventory_ids_once_allocated(app, client, admin_access, order_with_fg_items):
    headers = {"Authorization": f"Bearer {admin_access}"}
    item_ids = _allocate(app, client, headers, order_with_fg_items)

    with app.app_context():
        from app.models.finished_good_item import FinishedGoodItem

        expected = sorted(FinishedGoodItem.query.filter(FinishedGoodItem.id.in_(item_ids)).with_entities(FinishedGoodItem.inventory_id).all())
        expected = [e[0] for e in expected]

    get_resp = client.get(f"/api/v1/orders/{order_with_fg_items['order_id']}", headers=headers)
    assert get_resp.status_code == 200, get_resp.get_json()
    line = next(l for l in get_resp.get_json()["lines"] if l["id"] == str(order_with_fg_items["line_id"]))
    assert line["allocation"]["inventoryIds"] == expected


def test_pack_partial_then_full_line(app, client, admin_access, order_with_fg_items):
    headers = {"Authorization": f"Bearer {admin_access}"}
    _allocate(app, client, headers, order_with_fg_items)
    line_id = order_with_fg_items["line_id"]

    partial = client.post(f"/api/v1/orders/lines/{line_id}/pack", json={"quantity": "1"}, headers=headers)
    assert partial.status_code == 200, partial.get_json()
    line = next(l for l in partial.get_json()["lines"] if l["id"] == str(line_id))
    assert line["packedQty"] == "1.000000"
    assert partial.get_json()["packingStatus"] == "pending_packing"  # order-level flag - not every line is fully packed yet

    full = client.post(f"/api/v1/orders/lines/{line_id}/pack", json={"quantity": "1"}, headers=headers)
    assert full.status_code == 200, full.get_json()
    line = next(l for l in full.get_json()["lines"] if l["id"] == str(line_id))
    assert line["packedQty"] == "2.000000"
    assert full.get_json()["packingStatus"] == "packed"


def test_pack_more_than_allocated_is_rejected(app, client, admin_access, order_with_fg_items):
    headers = {"Authorization": f"Bearer {admin_access}"}
    _allocate(app, client, headers, order_with_fg_items)
    resp = client.post(f"/api/v1/orders/lines/{order_with_fg_items['line_id']}/pack", json={"quantity": "3"}, headers=headers)
    assert resp.status_code == 422, resp.get_json()
    assert resp.get_json()["code"] == "PACK_QTY_EXCEEDS_REMAINING"


def test_ship_requires_packed_first(app, client, admin_access, order_with_fg_items):
    headers = {"Authorization": f"Bearer {admin_access}"}
    _allocate(app, client, headers, order_with_fg_items)
    resp = client.post(f"/api/v1/orders/lines/{order_with_fg_items['line_id']}/ship", json={"quantity": "1"}, headers=headers)
    assert resp.status_code == 422, resp.get_json()
    assert resp.get_json()["code"] == "SHIP_QTY_EXCEEDS_PACKED"


def test_partial_ship_moves_exactly_that_much_stock_and_leaves_reservation_open(app, client, admin_access, order_with_fg_items):
    """The core "real partial shipment" behavior: shipping 1 of 2 packed
    units must debit exactly 1 unit's worth out of the reserved bucket,
    leave the reservation open (not issued) since half is still held, and
    leave the line at 'allocated' (not 'shipped') since it isn't done."""
    headers = {"Authorization": f"Bearer {admin_access}"}
    _allocate(app, client, headers, order_with_fg_items)
    line_id = order_with_fg_items["line_id"]
    fg_id = order_with_fg_items["fg_id"]
    tenant_id = order_with_fg_items["tenant_id"]

    client.post(f"/api/v1/orders/lines/{line_id}/pack", json={"quantity": "2"}, headers=headers)

    with app.app_context():
        reserved_before = _reserved_balance(tenant_id, fg_id)
    assert reserved_before == Decimal("2")

    ship_resp = client.post(f"/api/v1/orders/lines/{line_id}/ship", json={"quantity": "1"}, headers=headers)
    assert ship_resp.status_code == 200, ship_resp.get_json()
    body = ship_resp.get_json()
    line = next(l for l in body["lines"] if l["id"] == str(line_id))
    assert line["shippedQty"] == "1.000000"
    assert line["status"] == "allocated"  # not fully shipped yet
    assert body["status"] == "partially_shipped"

    with app.app_context():
        from app.models.order_line import OrderLine
        from app.models.reservation import Reservation

        reserved_after = _reserved_balance(tenant_id, fg_id)
        assert reserved_after == Decimal("1")

        line_row = OrderLine.query.filter_by(id=line_id).first()
        reservation = Reservation.query.filter_by(id=line_row.reservation_id).first()
        assert reservation.status == "open"  # half still held
        assert reservation.issued_qty == Decimal("1")


def test_second_partial_ship_completes_the_line_and_order(app, client, admin_access, order_with_fg_items):
    headers = {"Authorization": f"Bearer {admin_access}"}
    _allocate(app, client, headers, order_with_fg_items)
    line_id = order_with_fg_items["line_id"]
    fg_id = order_with_fg_items["fg_id"]
    tenant_id = order_with_fg_items["tenant_id"]

    client.post(f"/api/v1/orders/lines/{line_id}/pack", json={"quantity": "2"}, headers=headers)
    client.post(f"/api/v1/orders/lines/{line_id}/ship", json={"quantity": "1"}, headers=headers)
    final = client.post(f"/api/v1/orders/lines/{line_id}/ship", json={"quantity": "1"}, headers=headers)
    assert final.status_code == 200, final.get_json()
    body = final.get_json()
    line = next(l for l in body["lines"] if l["id"] == str(line_id))
    assert line["shippedQty"] == "2.000000"
    assert line["status"] == "shipped"
    assert body["status"] == "shipped"

    with app.app_context():
        from app.models.order_line import OrderLine
        from app.models.reservation import Reservation

        reserved_after = _reserved_balance(tenant_id, fg_id)
        assert reserved_after == Decimal("0")

        line_row = OrderLine.query.filter_by(id=line_id).first()
        reservation = Reservation.query.filter_by(id=line_row.reservation_id).first()
        assert reservation.status == "issued"
        assert reservation.issued_qty == Decimal("2")


def test_pack_after_fully_shipped_is_rejected(app, client, admin_access, order_with_fg_items):
    """Guards a real gap this feature can otherwise hit: a line whose
    packed_qty never got tracked (e.g. shipped through the legacy
    whole-order POST /orders/:id/ship, which sets shipped_qty straight to
    the line quantity without touching packed_qty) still reads
    allocated_qty > packed_qty once shipped - which, unguarded, would let
    pack_order_line "pack" a line that's already left the building."""
    headers = {"Authorization": f"Bearer {admin_access}"}
    _allocate(app, client, headers, order_with_fg_items)
    line_id = order_with_fg_items["line_id"]
    client.post(f"/api/v1/orders/lines/{line_id}/pack", json={"quantity": "2"}, headers=headers)
    client.post(f"/api/v1/orders/lines/{line_id}/ship", json={"quantity": "2"}, headers=headers)

    resp = client.post(f"/api/v1/orders/lines/{line_id}/pack", json={"quantity": "1"}, headers=headers)
    assert resp.status_code == 422, resp.get_json()
    assert resp.get_json()["code"] == "LINE_ALREADY_SHIPPED"
