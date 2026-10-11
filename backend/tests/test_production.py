"""New test coverage for the production domain port (no direct
original-repo equivalent - see test_orders.py's docstring for the same
note). Covers BOM-driven production posting (component consumption +
finished-good item creation + stage seeding), the insufficient-components
guard, additional (beyond-BOM) component add/remove, Daily Production
Planning -> Complete Production, stage-sequencing, and finished-good
transfer/status-change - all against a real Postgres. Component stock is
seeded directly via inventory_ledger.post() (bypassing GRN receiving, same
shortcut test_orders.py takes) since this suite only cares about the
production side of the workflow.
"""

from __future__ import annotations

import uuid

from app.core.db import SessionLocal


def _auth_headers(client, admin):
    login = client.post("/api/v1/auth/login", json={"email": admin["email"], "password": admin["password"]})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['accessToken']}"}


def _seed_stock(tenant_id, product_id: str, warehouse_id: str, quantity: str, uom: str) -> None:
    from app.services import inventory_ledger
    from app.services.inventory_ledger import LedgerPosting

    inventory_ledger.post(
        LedgerPosting(
            tenant_id=tenant_id,
            product_id=uuid.UUID(product_id),
            sku="",
            warehouse_id=uuid.UUID(warehouse_id),
            quantity=quantity,
            uom=uom,
            bucket="available",
            movement_type="receipt",
            reference_type="test-seed",
            reference_id=str(uuid.uuid4()),
        )
    )
    SessionLocal.commit()


def _cleanup_bom(bom_id: str) -> None:
    from app.models.bom import Bom
    from app.models.bom_component import BomComponent
    from app.models.bom_version import BomVersion

    bid = uuid.UUID(bom_id)
    version_ids = [v.id for v in BomVersion.query.filter_by(bom_id=bid).all()]
    if version_ids:
        BomComponent.query.filter(BomComponent.bom_version_id.in_(version_ids)).delete(synchronize_session=False)
    BomVersion.query.filter_by(bom_id=bid).delete(synchronize_session=False)
    Bom.query.filter_by(id=bid).delete(synchronize_session=False)
    SessionLocal.commit()


def _cleanup_production(run_id: str) -> None:
    from app.models.finished_good_item import FinishedGoodItem
    from app.models.production_consumption import ProductionConsumption
    from app.models.production_consumption_item import ProductionConsumptionItem
    from app.models.production_run import ProductionRun
    from app.models.production_run_stage import ProductionRunStage
    from app.models.stock_ledger import StockLedger

    rid = uuid.UUID(run_id)
    consumption_ids = [c.id for c in ProductionConsumption.query.filter_by(production_run_id=rid).all()]
    if consumption_ids:
        ProductionConsumptionItem.query.filter(ProductionConsumptionItem.production_consumption_id.in_(consumption_ids)).delete(synchronize_session=False)
    ProductionConsumption.query.filter_by(production_run_id=rid).delete(synchronize_session=False)
    ProductionRunStage.query.filter_by(production_run_id=rid).delete(synchronize_session=False)
    FinishedGoodItem.query.filter_by(production_run_id=rid).delete(synchronize_session=False)
    StockLedger.query.filter(StockLedger.reference_id.like(f"{rid}%")).delete(synchronize_session=False)
    ProductionRun.query.filter_by(id=rid).delete(synchronize_session=False)
    SessionLocal.commit()


def _cleanup_warehouse(warehouse_id: str) -> None:
    from app.models.location import Location
    from app.models.reservation import Reservation
    from app.models.stock_balance import StockBalance
    from app.models.stock_ledger import StockLedger
    from app.models.warehouse import Warehouse

    wid = uuid.UUID(warehouse_id)
    Reservation.query.filter_by(warehouse_id=wid).delete(synchronize_session=False)
    StockLedger.query.filter_by(warehouse_id=wid).delete(synchronize_session=False)
    StockBalance.query.filter_by(warehouse_id=wid).delete(synchronize_session=False)
    Location.query.filter_by(warehouse_id=wid).delete(synchronize_session=False)
    Warehouse.query.filter_by(id=wid).delete(synchronize_session=False)
    SessionLocal.commit()


def _cleanup_product(product_id: str) -> None:
    from app.models.product import Product
    from app.models.reservation import Reservation
    from app.models.stock_balance import StockBalance
    from app.models.stock_ledger import StockLedger

    pid = uuid.UUID(product_id)
    Reservation.query.filter_by(product_id=pid).delete(synchronize_session=False)
    StockLedger.query.filter_by(product_id=pid).delete(synchronize_session=False)
    StockBalance.query.filter_by(product_id=pid).delete(synchronize_session=False)
    Product.query.filter_by(id=pid).delete(synchronize_session=False)
    SessionLocal.commit()


def _setup(client, headers, default_tenant_id, *, rm1_stock="20", rm2_stock="20"):
    """One finished good with an approved BOM (2 KG rm1 @5% scrap + 1 UNIT
    rm2 per FG unit), a warehouse, and rm1/rm2 stock seeded directly into
    `available`."""
    suffix = uuid.uuid4().hex[:8]
    warehouse = client.post("/api/v1/warehouses", headers=headers, json={"name": f"PRD Test WH {suffix}"}).json()
    fg = client.post("/api/v1/products", headers=headers, json={"sku": f"PRD-FG-{suffix}", "name": f"PRD Test Assembly {suffix}", "make": "TestCo", "type": "finished_good", "uom": "UNIT"}).json()
    rm1 = client.post("/api/v1/products", headers=headers, json={"sku": f"PRD-RM1-{suffix}", "name": f"PRD Test Material One {suffix}", "make": "TestCo", "type": "raw_material", "uom": "KG"}).json()
    rm2 = client.post("/api/v1/products", headers=headers, json={"sku": f"PRD-RM2-{suffix}", "name": f"PRD Test Material Two {suffix}", "make": "TestCo", "type": "consumable", "uom": "UNIT"}).json()

    bom = client.post(
        "/api/v1/boms",
        headers=headers,
        json={
            "productId": fg["id"],
            "effectiveFrom": "2026-01-01",
            "components": [
                {"componentProductId": rm1["id"], "quantity": "2", "uom": "KG", "scrapPercent": "5"},
                {"componentProductId": rm2["id"], "quantity": "1", "uom": "UNIT"},
            ],
        },
    ).json()

    _seed_stock(default_tenant_id, rm1["id"], warehouse["id"], rm1_stock, "KG")
    _seed_stock(default_tenant_id, rm2["id"], warehouse["id"], rm2_stock, "UNIT")

    return warehouse, fg, rm1, rm2, bom


def _teardown(bom, warehouse, fg, rm1, rm2):
    _cleanup_bom(bom["id"])
    _cleanup_warehouse(warehouse["id"])
    for p in (fg, rm1, rm2):
        _cleanup_product(p["id"])


def test_post_production_consumes_bom_and_creates_finished_goods(client, fresh_admin, default_tenant_id):
    headers = _auth_headers(client, fresh_admin)
    warehouse, fg, rm1, rm2, bom = _setup(client, headers, default_tenant_id)

    create = client.post(
        "/api/v1/inventory/production",
        headers=headers,
        json={"productId": fg["id"], "quantity": "3", "uom": "UNIT", "warehouseId": warehouse["id"]},
    )
    assert create.status_code == 201, create.text
    body = create.json()
    consumed_by_sku = {c["sku"]: c for c in body["consumed"]}
    # 3 units * 2 KG * 1.05 scrap factor = 6.3 KG; 3 units * 1 UNIT = 3 UNIT.
    assert consumed_by_sku[rm1["sku"]]["quantity"] == "6.300000"
    assert consumed_by_sku[rm1["sku"]]["isAdditional"] is False
    assert consumed_by_sku[rm2["sku"]]["quantity"] == "3.000000"

    get_resp = client.get(f"/api/v1/inventory/production/{body['id']}", headers=headers)
    assert get_resp.status_code == 200, get_resp.text
    run = get_resp.json()
    assert run["status"] == "posted"
    assert run["bomVersion"] == 1
    assert len(run["finishedGoods"]) == 3
    assert all(fgi["kind"] == "piece" and fgi["quantity"] == "1.000000" for fgi in run["finishedGoods"])
    assert {s["stageKey"] for s in run["stages"]} == {"cell_testing", "module_assembly", "cell_assembly", "frp_cutting", "bms_sensing_cable_assembly", "enclosure_assembly", "qc_pdi"}
    assert all(s["completedAt"] is None for s in run["stages"])

    balances = client.get("/api/v1/inventory/balances", headers=headers, params={"productId": rm1["id"], "warehouseId": warehouse["id"]}).json()["data"]
    assert sum(float(r["available"]) for r in balances) == 20.0 - 6.3

    finished_goods = client.get("/api/v1/inventory/finished-goods", headers=headers, params={"productionRunId": body["id"]}).json()["data"]
    assert len(finished_goods) == 3

    _cleanup_production(body["id"])
    _teardown(bom, warehouse, fg, rm1, rm2)


def test_post_production_rejects_insufficient_components(client, fresh_admin, default_tenant_id):
    headers = _auth_headers(client, fresh_admin)
    warehouse, fg, rm1, rm2, bom = _setup(client, headers, default_tenant_id, rm1_stock="1")

    create = client.post(
        "/api/v1/inventory/production",
        headers=headers,
        json={"productId": fg["id"], "quantity": "3", "uom": "UNIT", "warehouseId": warehouse["id"]},
    )
    assert create.status_code == 422, create.text
    assert create.json()["code"] == "INSUFFICIENT_COMPONENTS"

    _teardown(bom, warehouse, fg, rm1, rm2)


def test_additional_component_add_and_remove(client, fresh_admin, default_tenant_id):
    headers = _auth_headers(client, fresh_admin)
    warehouse, fg, rm1, rm2, bom = _setup(client, headers, default_tenant_id)

    run_id = client.post("/api/v1/inventory/production", headers=headers, json={"productId": fg["id"], "quantity": "1", "uom": "UNIT", "warehouseId": warehouse["id"]}).json()["id"]

    add = client.post(f"/api/v1/inventory/production/{run_id}/additional-components", headers=headers, json={"productId": rm2["id"], "quantity": "2", "uom": "UNIT"})
    assert add.status_code == 200, add.text
    additional = [c for c in add.json() if c["isAdditional"]]
    assert len(additional) == 1
    assert additional[0]["quantity"] == "2.000000"
    assert additional[0]["removable"] is True
    consumption_id = additional[0]["id"]

    balances = client.get("/api/v1/inventory/balances", headers=headers, params={"productId": rm2["id"], "warehouseId": warehouse["id"]}).json()["data"]
    # 20 seeded - 1 BOM-required - 2 additional = 17.
    assert sum(float(r["available"]) for r in balances) == 17.0

    remove = client.delete(f"/api/v1/inventory/production/{run_id}/additional-components/{consumption_id}", headers=headers)
    assert remove.status_code == 200, remove.text
    assert not [c for c in remove.json() if c["isAdditional"]]

    balances_after = client.get("/api/v1/inventory/balances", headers=headers, params={"productId": rm2["id"], "warehouseId": warehouse["id"]}).json()["data"]
    assert sum(float(r["available"]) for r in balances_after) == 19.0

    _cleanup_production(run_id)
    _teardown(bom, warehouse, fg, rm1, rm2)


def test_plan_then_complete_production(client, fresh_admin, default_tenant_id):
    headers = _auth_headers(client, fresh_admin)
    warehouse, fg, rm1, rm2, bom = _setup(client, headers, default_tenant_id)

    plan = client.post("/api/v1/inventory/production/plan", headers=headers, json={"productionDate": "2026-06-01", "warehouseId": warehouse["id"], "items": [{"productId": fg["id"], "packId": "PACK-001"}]})
    assert plan.status_code == 201, plan.text
    planned = plan.json()["data"][0]
    assert planned["status"] == "planned"
    assert planned["packId"] == "PACK-001"

    complete = client.post(f"/api/v1/inventory/production/{planned['id']}/complete", headers=headers, json={"batchNo": None})
    assert complete.status_code == 200, complete.text
    result = complete.json()
    assert result["number"] == planned["number"]

    run = client.get(f"/api/v1/inventory/production/{planned['id']}", headers=headers).json()
    assert run["status"] == "posted"
    assert run["packId"] == "PACK-001"
    assert len(run["finishedGoods"]) == 1  # planned rows default to quantity=1 UNIT

    _cleanup_production(planned["id"])
    _teardown(bom, warehouse, fg, rm1, rm2)


def test_stage_completion_enforces_sequence(client, fresh_admin, default_tenant_id):
    headers = _auth_headers(client, fresh_admin)
    warehouse, fg, rm1, rm2, bom = _setup(client, headers, default_tenant_id)
    run_id = client.post("/api/v1/inventory/production", headers=headers, json={"productId": fg["id"], "quantity": "1", "uom": "UNIT", "warehouseId": warehouse["id"]}).json()["id"]

    out_of_order = client.post(f"/api/v1/inventory/production/{run_id}/stages/module_assembly/complete", headers=headers, json={"associateName": "Priya"})
    assert out_of_order.status_code == 422
    assert out_of_order.json()["code"] == "STAGE_OUT_OF_SEQUENCE"

    in_order = client.post(f"/api/v1/inventory/production/{run_id}/stages/cell_testing/complete", headers=headers, json={"associateName": "Priya"})
    assert in_order.status_code == 200, in_order.text
    stages_by_key = {s["stageKey"]: s for s in in_order.json()["stages"]}
    assert stages_by_key["cell_testing"]["completedAt"] is not None
    assert stages_by_key["cell_testing"]["associateName"] == "Priya"

    already_done = client.post(f"/api/v1/inventory/production/{run_id}/stages/cell_testing/complete", headers=headers, json={"associateName": "Priya"})
    assert already_done.status_code == 422
    assert already_done.json()["code"] == "STAGE_ALREADY_DONE"

    _cleanup_production(run_id)
    _teardown(bom, warehouse, fg, rm1, rm2)


def test_finished_good_transfer_and_status_change(client, fresh_admin, default_tenant_id):
    headers = _auth_headers(client, fresh_admin)
    warehouse, fg, rm1, rm2, bom = _setup(client, headers, default_tenant_id)
    run_id = client.post("/api/v1/inventory/production", headers=headers, json={"productId": fg["id"], "quantity": "1", "uom": "UNIT", "warehouseId": warehouse["id"]}).json()["id"]
    fg_item = client.get("/api/v1/inventory/finished-goods", headers=headers, params={"productionRunId": run_id}).json()["data"][0]

    other_warehouse = client.post("/api/v1/warehouses", headers=headers, json={"name": f"PRD Test WH2 {uuid.uuid4().hex[:6]}"}).json()
    transfer = client.post(f"/api/v1/inventory/finished-goods/{fg_item['id']}/transfer", headers=headers, json={"toWarehouseId": other_warehouse["id"], "reason": "Testing FG transfer"})
    assert transfer.status_code == 200, transfer.text
    assert transfer.json()["warehouseId"] == other_warehouse["id"]

    status_change = client.post(f"/api/v1/inventory/finished-goods/{fg_item['id']}/status", headers=headers, json={"toStatus": "quarantine", "reason": "Testing FG status change"})
    assert status_change.status_code == 200, status_change.text
    assert status_change.json()["status"] == "quarantine"

    _cleanup_production(run_id)
    _cleanup_warehouse(other_warehouse["id"])
    _teardown(bom, warehouse, fg, rm1, rm2)
