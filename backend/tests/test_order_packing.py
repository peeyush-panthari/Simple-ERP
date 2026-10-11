"""Production > Order Shipping's Packed flag - POST /orders/<id>/pack, and
the new gate on POST /orders/<id>/ship that requires it first. Order.
packing_status is independent of Order.status (see order.py/orders.py) -
these tests cover both the pack action's own status-window guard and the
ship-side gate it now enforces."""

import uuid
from datetime import date, timedelta

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
        fg = Product(tenant_id=default_tenant_id, sku=f"TST-PACK-{suffix}", name="Order Packing Test FG", type="finished_good", uom="UNIT", status="active")
        warehouse = Warehouse(tenant_id=default_tenant_id, code=f"WH-PACK-{suffix}", name="Order Packing Test Warehouse", status="active")
        customer = Party(tenant_id=default_tenant_id, code=f"CUST-PACK-{suffix}", legal_name="Test Customer Ltd", display_name="Test Customer", type="customer", status="active")
        _db.session.add_all([fg, warehouse, customer])
        _db.session.flush()

        bom = Bom(tenant_id=default_tenant_id, product_id=fg.id, product_sku=fg.sku, status="active")
        _db.session.add(bom)
        _db.session.flush()
        version = BomVersion(tenant_id=default_tenant_id, bom_id=bom.id, version=1, state="approved", yield_percent=100, effective_from=date.today() - timedelta(days=1))
        _db.session.add(version)

        order = Order(tenant_id=default_tenant_id, number=f"SO-PACK-{suffix}", customer_id=customer.id, customer_name=customer.display_name, status="confirmed", promised_date=date.today() + timedelta(days=7), warehouse_id=warehouse.id, total="200")
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


def _allocate(app, client, headers, ctx):
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


def test_pack_requires_allocated_status(client, admin_access, order_with_fg_items):
    resp = client.post(f"/api/v1/orders/{order_with_fg_items['order_id']}/pack", headers={"Authorization": f"Bearer {admin_access}"})
    assert resp.status_code == 422, resp.get_json()
    assert resp.get_json()["code"] == "ORDER_NOT_ALLOCATED"


def test_pack_succeeds_once_allocated(app, client, admin_access, order_with_fg_items):
    headers = {"Authorization": f"Bearer {admin_access}"}
    _allocate(app, client, headers, order_with_fg_items)

    get_before = client.get(f"/api/v1/orders/{order_with_fg_items['order_id']}", headers=headers)
    assert get_before.get_json()["packingStatus"] == "pending_packing"

    pack_resp = client.post(f"/api/v1/orders/{order_with_fg_items['order_id']}/pack", headers=headers)
    assert pack_resp.status_code == 200, pack_resp.get_json()
    assert pack_resp.get_json()["packingStatus"] == "packed"


def test_ship_is_blocked_until_packed_then_succeeds(app, client, admin_access, order_with_fg_items):
    headers = {"Authorization": f"Bearer {admin_access}"}
    _allocate(app, client, headers, order_with_fg_items)

    blocked = client.post(f"/api/v1/orders/{order_with_fg_items['order_id']}/ship", headers=headers)
    assert blocked.status_code == 422, blocked.get_json()
    assert blocked.get_json()["code"] == "ORDER_NOT_PACKED"

    pack_resp = client.post(f"/api/v1/orders/{order_with_fg_items['order_id']}/pack", headers=headers)
    assert pack_resp.status_code == 200, pack_resp.get_json()

    ship_resp = client.post(f"/api/v1/orders/{order_with_fg_items['order_id']}/ship", headers=headers)
    assert ship_resp.status_code == 200, ship_resp.get_json()
    assert ship_resp.get_json()["status"] == "shipped"
