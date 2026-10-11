"""New test coverage for the warehouses + inventory domain port (no direct
original-repo equivalent - see test_orders.py's docstring for the same
note). Covers warehouse/location CRUD, adjustments (the real way stock
enters `available` now that GRN receiving isn't ported yet), transfers
(dispatch + complete, in_transit -> available), and status-change, all
against a real Postgres.
"""

from __future__ import annotations

import uuid

import pytest

from app.core.db import SessionLocal


@pytest.fixture
def product(default_tenant_id):
    from app.models.product import Product

    p = Product(
        tenant_id=default_tenant_id,
        sku=f"RM-TEST-{uuid.uuid4().hex[:8]}",
        name="Test Raw Material",
        type="raw_material",
        uom="KG",
        status="active",
        sellable=False,
        purchasable=True,
    )
    SessionLocal.add(p)
    SessionLocal.commit()
    yield p

    from app.models.reservation import Reservation
    from app.models.stock_balance import StockBalance
    from app.models.stock_ledger import StockLedger

    Reservation.query.filter_by(product_id=p.id).delete(synchronize_session=False)
    StockLedger.query.filter_by(product_id=p.id).delete(synchronize_session=False)
    StockBalance.query.filter_by(product_id=p.id).delete(synchronize_session=False)
    Product.query.filter_by(id=p.id).delete(synchronize_session=False)
    SessionLocal.commit()


def _auth_headers(client, fresh_admin):
    login = client.post("/api/v1/auth/login", json={"email": fresh_admin["email"], "password": fresh_admin["password"]})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['accessToken']}"}


@pytest.fixture
def warehouse_pair(client, fresh_admin, default_tenant_id):
    """Two warehouses created through the real API, cleaned up after."""
    headers = _auth_headers(client, fresh_admin)
    created = []
    for i in range(2):
        resp = client.post(
            "/api/v1/warehouses",
            headers=headers,
            json={"name": f"Test WH {i}-{uuid.uuid4().hex[:6]}"},
        )
        assert resp.status_code == 201, resp.text
        created.append(resp.json())
    yield created

    from app.models.location import Location
    from app.models.reservation import Reservation
    from app.models.stock_balance import StockBalance
    from app.models.stock_ledger import StockLedger
    from app.models.transfer import Transfer
    from app.models.warehouse import Warehouse

    for w in created:
        wid = uuid.UUID(w["id"])
        # Torn down before the `product` fixture's own cleanup runs (pytest
        # tears down in reverse dependency order, and this fixture doesn't
        # depend on `product`), so it must independently clear everything
        # FK-RESTRICTed to this warehouse, not just what it created itself.
        Reservation.query.filter_by(warehouse_id=wid).delete(synchronize_session=False)
        StockLedger.query.filter_by(warehouse_id=wid).delete(synchronize_session=False)
        StockBalance.query.filter_by(warehouse_id=wid).delete(synchronize_session=False)
        Transfer.query.filter((Transfer.source_warehouse_id == wid) | (Transfer.dest_warehouse_id == wid)).delete(synchronize_session=False)
        Location.query.filter_by(warehouse_id=wid).delete(synchronize_session=False)
        Warehouse.query.filter_by(id=wid).delete(synchronize_session=False)
    SessionLocal.commit()


def test_create_warehouse_seeds_quarantine_location(client, fresh_admin):
    headers = _auth_headers(client, fresh_admin)
    resp = client.post("/api/v1/warehouses", headers=headers, json={"name": f"Test Warehouse {uuid.uuid4().hex[:6]}"})
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["code"]

    locations = client.get(f"/api/v1/warehouses/{body['id']}/locations", headers=headers)
    assert locations.status_code == 200
    codes = [l["code"] for l in locations.json()["data"]]
    assert "QUARANTINE" in codes

    from app.models.location import Location
    from app.models.warehouse import Warehouse

    Location.query.filter_by(warehouse_id=uuid.UUID(body["id"])).delete(synchronize_session=False)
    Warehouse.query.filter_by(id=uuid.UUID(body["id"])).delete(synchronize_session=False)
    SessionLocal.commit()


def test_duplicate_warehouse_code_rejected(client, fresh_admin):
    headers = _auth_headers(client, fresh_admin)
    code = f"DUP{uuid.uuid4().hex[:6].upper()}"
    first = client.post("/api/v1/warehouses", headers=headers, json={"name": "First", "code": code})
    assert first.status_code == 201
    second = client.post("/api/v1/warehouses", headers=headers, json={"name": "Second", "code": code})
    assert second.status_code == 409
    assert second.json()["code"] == "WAREHOUSE_CODE_TAKEN"

    from app.models.location import Location
    from app.models.warehouse import Warehouse

    wid = uuid.UUID(first.json()["id"])
    Location.query.filter_by(warehouse_id=wid).delete(synchronize_session=False)
    Warehouse.query.filter_by(id=wid).delete(synchronize_session=False)
    SessionLocal.commit()


def test_adjustment_moves_stock_into_available_and_ledger_records_it(client, fresh_admin, product, warehouse_pair):
    headers = _auth_headers(client, fresh_admin)
    warehouse = warehouse_pair[0]

    resp = client.post(
        "/api/v1/inventory/adjustments",
        headers=headers,
        json={
            "productId": str(product.id),
            "warehouseId": warehouse["id"],
            "quantity": "100",
            "uom": "KG",
            "bucket": "available",
            "reason": "Opening balance for testing",
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["reference"].startswith("ADJ-")

    balances = client.get("/api/v1/inventory/balances", headers=headers, params={"productId": str(product.id)})
    assert balances.status_code == 200
    rows = balances.json()["data"]
    assert len(rows) == 1
    assert rows[0]["available"] == "100.000000"

    ledger = client.get("/api/v1/inventory/ledger", headers=headers, params={"productId": str(product.id)})
    assert ledger.status_code == 200
    assert ledger.json()["meta"]["total"] == 1
    assert ledger.json()["data"][0]["movementType"] == "adjustment"


def test_negative_adjustment_beyond_available_rejected(client, fresh_admin, product, warehouse_pair):
    headers = _auth_headers(client, fresh_admin)
    warehouse = warehouse_pair[0]

    resp = client.post(
        "/api/v1/inventory/adjustments",
        headers=headers,
        json={"productId": str(product.id), "warehouseId": warehouse["id"], "quantity": "-5", "uom": "KG", "bucket": "available", "reason": "Attempt write-off with nothing on hand"},
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "INSUFFICIENT_STOCK"


def test_transfer_dispatch_and_complete_moves_stock_between_warehouses(client, fresh_admin, product, warehouse_pair):
    headers = _auth_headers(client, fresh_admin)
    source, dest = warehouse_pair

    seed = client.post(
        "/api/v1/inventory/adjustments",
        headers=headers,
        json={"productId": str(product.id), "warehouseId": source["id"], "quantity": "50", "uom": "KG", "bucket": "available", "reason": "Seed stock for transfer test"},
    )
    assert seed.status_code == 201

    transfer = client.post(
        "/api/v1/inventory/transfers",
        headers=headers,
        json={"productId": str(product.id), "quantity": "20", "uom": "KG", "sourceWarehouseId": source["id"], "destWarehouseId": dest["id"]},
    )
    assert transfer.status_code == 201, transfer.text
    transfer_id = transfer.json()["id"]
    assert transfer.json()["status"] == "in_transit"

    source_balances = client.get("/api/v1/inventory/balances", headers=headers, params={"productId": str(product.id), "warehouseId": source["id"]}).json()["data"]
    assert source_balances[0]["available"] == "30.000000"

    dest_balances_before = client.get("/api/v1/inventory/balances", headers=headers, params={"productId": str(product.id), "warehouseId": dest["id"]}).json()["data"]
    assert dest_balances_before[0]["inTransit"] == "20.000000"
    assert dest_balances_before[0]["available"] == "0.000000"

    complete = client.post(f"/api/v1/inventory/transfers/{transfer_id}/complete", headers=headers, json={})
    assert complete.status_code == 200, complete.text
    assert complete.json()["status"] == "completed"

    dest_balances_after = client.get("/api/v1/inventory/balances", headers=headers, params={"productId": str(product.id), "warehouseId": dest["id"]}).json()["data"]
    assert dest_balances_after[0]["available"] == "20.000000"
    assert dest_balances_after[0]["inTransit"] == "0.000000"


def test_status_change_moves_between_buckets(client, fresh_admin, product, warehouse_pair):
    headers = _auth_headers(client, fresh_admin)
    warehouse = warehouse_pair[0]

    client.post(
        "/api/v1/inventory/adjustments",
        headers=headers,
        json={"productId": str(product.id), "warehouseId": warehouse["id"], "quantity": "10", "uom": "KG", "bucket": "available", "reason": "Seed stock for status-change test"},
    )

    resp = client.post(
        "/api/v1/inventory/status-change",
        headers=headers,
        json={"productId": str(product.id), "warehouseId": warehouse["id"], "quantity": "4", "uom": "KG", "from": "available", "to": "quarantine", "reason": "QC recheck requested"},
    )
    assert resp.status_code == 201, resp.text

    balances = client.get("/api/v1/inventory/balances", headers=headers, params={"productId": str(product.id), "warehouseId": warehouse["id"]}).json()["data"]
    assert balances[0]["available"] == "6.000000"
    assert balances[0]["quarantine"] == "4.000000"
