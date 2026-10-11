"""Daily Production Planning / Complete Production - POST /inventory/
production/plan bulk-creates bare 'planned' ProductionRun rows, and POST
/inventory/production/<id>/complete finishes one of them through the exact
same BOM-explode/consume/create-FG core direct creation uses (see
_post_production's existing_run branch in inventory_movements.py). Reuses
test_finished_good_items.py's zero-component-BOM fixture pattern so
completion can be exercised through the real API without seeding raw
material stock."""

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
        fg = Product(tenant_id=default_tenant_id, sku=f"TST-PLN-{suffix}", name="Production Planning Test FG", type="finished_good", uom="UNIT", status="active")
        rm = Product(tenant_id=default_tenant_id, sku=f"TST-PLNRM-{suffix}", name="Production Planning Test RM", type="raw_material", uom="KG", status="active")
        warehouse = Warehouse(tenant_id=default_tenant_id, code=f"WH-PLN-{suffix}", name="Production Planning Test Warehouse", status="active")
        _db.session.add_all([fg, rm, warehouse])
        _db.session.flush()

        bom = Bom(tenant_id=default_tenant_id, product_id=fg.id, product_sku=fg.sku, status="active")
        _db.session.add(bom)
        _db.session.flush()
        version = BomVersion(tenant_id=default_tenant_id, bom_id=bom.id, version=1, state="approved", yield_percent=100, effective_from=date.today() - timedelta(days=1))
        _db.session.add(version)
        _db.session.commit()

        ids = {"tenant_id": default_tenant_id, "fg_id": fg.id, "fg_sku": fg.sku, "rm_id": rm.id, "warehouse_id": warehouse.id}
        yield ids

        from app.models.finished_good_item import FinishedGoodItem
        from app.models.production_run import ProductionRun
        from app.models.stock_balance import StockBalance
        from app.models.stock_ledger import StockLedger

        FinishedGoodItem.query.filter_by(product_id=fg.id).delete(synchronize_session=False)
        StockLedger.query.filter_by(product_id=fg.id).delete(synchronize_session=False)
        StockBalance.query.filter_by(product_id=fg.id).delete(synchronize_session=False)
        ProductionRun.query.filter_by(product_id=fg.id).delete(synchronize_session=False)
        BomVersion.query.filter_by(bom_id=bom.id).delete(synchronize_session=False)
        Bom.query.filter_by(id=bom.id).delete(synchronize_session=False)
        Product.query.filter_by(id=fg.id).delete(synchronize_session=False)
        Product.query.filter_by(id=rm.id).delete(synchronize_session=False)
        Warehouse.query.filter_by(id=warehouse.id).delete(synchronize_session=False)
        _db.session.commit()


@pytest.fixture
def admin_access(client, fresh_admin):
    resp = client.post("/api/v1/auth/login", json={"email": fresh_admin["email"], "password": fresh_admin["password"]})
    return resp.get_json()["accessToken"]


def test_plan_creates_bare_planned_runs(app, client, admin_access, producible_fg):
    headers = {"Authorization": f"Bearer {admin_access}"}
    resp = client.post(
        "/api/v1/inventory/production/plan",
        json={
            "productionDate": date.today().isoformat(),
            "warehouseId": str(producible_fg["warehouse_id"]),
            "items": [{"productId": str(producible_fg["fg_id"]), "packId": "PACK-001"}, {"productId": str(producible_fg["fg_id"]), "packId": "PACK-002"}],
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.get_json()
    runs = resp.get_json()["data"]
    assert len(runs) == 2
    pack_ids = {r["packId"] for r in runs}
    assert pack_ids == {"PACK-001", "PACK-002"}
    for r in runs:
        assert r["status"] == "planned"
        assert r["quantity"] == "1.000000"
        assert r["uom"] == "UNIT"
        assert r["batchNo"] is None
        assert r["number"].startswith("PRD-")

    with app.app_context():
        from app.models.production_run import ProductionRun
        from app.models.production_run_stage import ProductionRunStage

        db_runs = ProductionRun.query.filter(ProductionRun.id.in_([r["id"] for r in runs])).all()
        assert all(r.status == "planned" for r in db_runs)
        # No stage checklist yet - that's only seeded once the run is
        # actually completed.
        assert ProductionRunStage.query.filter(ProductionRunStage.production_run_id.in_([r.id for r in db_runs])).count() == 0


def test_plan_rejects_non_finished_good(client, admin_access, producible_fg):
    resp = client.post(
        "/api/v1/inventory/production/plan",
        json={"productionDate": date.today().isoformat(), "warehouseId": str(producible_fg["warehouse_id"]), "items": [{"productId": str(producible_fg["rm_id"])}]},
        headers={"Authorization": f"Bearer {admin_access}"},
    )
    assert resp.status_code == 422, resp.get_json()
    assert resp.get_json()["code"] == "NOT_A_FINISHED_GOOD"


def test_complete_planned_run_posts_it_and_creates_fg_item(app, client, admin_access, producible_fg):
    headers = {"Authorization": f"Bearer {admin_access}"}
    plan_resp = client.post(
        "/api/v1/inventory/production/plan",
        json={"productionDate": date.today().isoformat(), "warehouseId": str(producible_fg["warehouse_id"]), "items": [{"productId": str(producible_fg["fg_id"]), "packId": "PACK-100"}]},
        headers=headers,
    )
    assert plan_resp.status_code == 201, plan_resp.get_json()
    run = plan_resp.get_json()["data"][0]

    complete_resp = client.post(f"/api/v1/inventory/production/{run['id']}/complete", json={"batchNo": "BATCH-1", "notes": "Completed in test"}, headers=headers)
    assert complete_resp.status_code == 200, complete_resp.get_json()
    assert complete_resp.get_json()["number"] == run["number"]

    get_resp = client.get(f"/api/v1/inventory/production/{run['id']}", headers=headers)
    assert get_resp.status_code == 200, get_resp.get_json()
    posted = get_resp.get_json()
    assert posted["status"] == "posted"
    assert posted["packId"] == "PACK-100"  # unchanged - locked at planning time
    assert posted["batchNo"] == "BATCH-1"
    assert posted["notes"] == "Completed in test"

    with app.app_context():
        from app.models.finished_good_item import FinishedGoodItem
        from app.models.production_run_stage import ProductionRunStage

        items = FinishedGoodItem.query.filter_by(production_run_id=run["id"]).all()
        assert len(items) == 1
        assert items[0].batch_no == "BATCH-1"
        # Stage checklist is seeded now, at completion time.
        assert ProductionRunStage.query.filter_by(production_run_id=run["id"]).count() == 7


def test_complete_already_posted_run_is_rejected(client, admin_access, producible_fg):
    headers = {"Authorization": f"Bearer {admin_access}"}
    direct_resp = client.post(
        "/api/v1/inventory/production",
        json={"productId": str(producible_fg["fg_id"]), "quantity": "1", "uom": "UNIT", "warehouseId": str(producible_fg["warehouse_id"])},
        headers=headers,
    )
    assert direct_resp.status_code == 201, direct_resp.get_json()
    run_id = direct_resp.get_json()["id"]

    resp = client.post(f"/api/v1/inventory/production/{run_id}/complete", json={}, headers=headers)
    assert resp.status_code == 422, resp.get_json()
    assert resp.get_json()["code"] == "PRODUCTION_NOT_PLANNED"


def test_complete_nonexistent_run_is_404(client, admin_access):
    resp = client.post(f"/api/v1/inventory/production/{uuid.uuid4()}/complete", json={}, headers={"Authorization": f"Bearer {admin_access}"})
    assert resp.status_code == 404


def test_direct_create_still_works_unchanged(app, client, admin_access, producible_fg):
    """Guards the _post_production refactor: a direct single-step create
    (no planning involved) must still insert its own fresh 'posted' row,
    exactly as before existing_run was introduced."""
    headers = {"Authorization": f"Bearer {admin_access}"}
    resp = client.post(
        "/api/v1/inventory/production",
        json={"productId": str(producible_fg["fg_id"]), "quantity": "2", "uom": "UNIT", "warehouseId": str(producible_fg["warehouse_id"]), "packId": "DIRECT-1"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.get_json()
    run_id = resp.get_json()["id"]

    with app.app_context():
        from app.models.production_run import ProductionRun

        run = ProductionRun.query.filter_by(id=run_id).first()
        assert run.status == "posted"
        assert run.pack_id == "DIRECT-1"
        assert run.quantity == Decimal("2")


def test_list_production_filters_by_search_and_date_range(app, client, admin_access, producible_fg):
    """GET /inventory/production's q param must match packId as well as the
    number/sku it already matched, and the new productionDateFrom/To params
    must bound on production_date - both back the new Production Runs tab
    search bar and date-range filter. Uses `in`/`not in` (not set equality)
    and self-cleans in a finally block, since this tenant's production table
    already carries rows from other tests/demo data - equality would make
    the assertion depend on exactly what else happens to exist."""
    headers = {"Authorization": f"Bearer {admin_access}"}
    today = date.today()
    pack_id = f"PACK-SEARCH-{producible_fg['fg_sku']}"
    plan_resp = client.post(
        "/api/v1/inventory/production/plan",
        json={
            "productionDate": today.isoformat(),
            "warehouseId": str(producible_fg["warehouse_id"]),
            "items": [{"productId": str(producible_fg["fg_id"]), "packId": pack_id}],
        },
        headers=headers,
    )
    assert plan_resp.status_code == 201, plan_resp.get_json()
    run = plan_resp.get_json()["data"][0]

    try:
        by_pack = client.get("/api/v1/inventory/production", query_string={"q": pack_id}, headers=headers)
        assert by_pack.status_code == 200, by_pack.get_json()
        assert run["id"] in {r["id"] for r in by_pack.get_json()["data"]}

        by_number = client.get("/api/v1/inventory/production", query_string={"q": run["number"]}, headers=headers)
        assert run["id"] in {r["id"] for r in by_number.get_json()["data"]}

        in_range = client.get(
            "/api/v1/inventory/production",
            query_string={"productionDateFrom": today.isoformat(), "productionDateTo": today.isoformat(), "warehouseId": str(producible_fg["warehouse_id"])},
            headers=headers,
        )
        assert run["id"] in {r["id"] for r in in_range.get_json()["data"]}

        out_of_range = client.get(
            "/api/v1/inventory/production",
            query_string={"productionDateFrom": (today + timedelta(days=1)).isoformat(), "warehouseId": str(producible_fg["warehouse_id"])},
            headers=headers,
        )
        assert run["id"] not in {r["id"] for r in out_of_range.get_json()["data"]}
    finally:
        with app.app_context():
            from app.models.production_run import ProductionRun

            ProductionRun.query.filter_by(id=run["id"]).delete(synchronize_session=False)
            _db.session.commit()
