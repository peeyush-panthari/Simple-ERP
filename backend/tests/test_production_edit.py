"""New coverage for PATCH /inventory/production/<id> - editing the
descriptive battery-pack traceability fields on an already-posted run. No
prior test exercised the production-run routes at all, so this fixture
constructs a ProductionRun directly rather than going through the full
BOM-explosion/stock-consumption post flow, which PATCH never touches."""

import uuid

import pytest

from tests.flaskcompat import db as _db


@pytest.fixture
def posted_run(app, default_tenant_id):
    from app.models.product import Product
    from app.models.production_run import ProductionRun
    from app.models.warehouse import Warehouse

    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        product = Product(tenant_id=default_tenant_id, sku=f"TST-PROD-{suffix}", name="Edit Test Finished Good", type="finished_good", uom="UNIT")
        warehouse = Warehouse(tenant_id=default_tenant_id, code=f"WH-PRD-{suffix}", name="Edit Test Warehouse", status="active")
        _db.session.add_all([product, warehouse])
        _db.session.flush()
        run = ProductionRun(
            tenant_id=default_tenant_id,
            number=f"PRD-TST-{suffix}",
            product_id=product.id,
            sku=product.sku,
            quantity="1",
            uom="UNIT",
            warehouse_id=warehouse.id,
            screen_type="Original screen",
        )
        _db.session.add(run)
        _db.session.commit()
        run_id, product_id, warehouse_id = run.id, product.id, warehouse.id
        yield {"tenant_id": default_tenant_id, "run_id": run_id}

        ProductionRun.query.filter_by(id=run_id).delete(synchronize_session=False)
        Product.query.filter_by(id=product_id).delete(synchronize_session=False)
        Warehouse.query.filter_by(id=warehouse_id).delete(synchronize_session=False)
        _db.session.commit()


@pytest.fixture
def admin_access(client, fresh_admin):
    resp = client.post("/api/v1/auth/login", json={"email": fresh_admin["email"], "password": fresh_admin["password"]})
    return resp.get_json()["accessToken"]


def test_update_production_edits_metadata_and_persists(client, admin_access, posted_run):
    run_id = posted_run["run_id"]
    resp = client.patch(
        f"/api/v1/inventory/production/{run_id}",
        json={"screenType": "AMOLED 5-inch", "notes": "Corrected after QC review", "cellsQuantity": 16},
        headers={"Authorization": f"Bearer {admin_access}"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["screenType"] == "AMOLED 5-inch"
    assert body["notes"] == "Corrected after QC review"
    assert body["cellsQuantity"] == 16
    assert body["status"] == "posted"

    fetched = client.get(f"/api/v1/inventory/production/{run_id}", headers={"Authorization": f"Bearer {admin_access}"})
    assert fetched.status_code == 200
    fetched_body = fetched.get_json()
    assert fetched_body["screenType"] == "AMOLED 5-inch"
    assert fetched_body["notes"] == "Corrected after QC review"
    assert fetched_body["cellsQuantity"] == 16


def test_update_production_rejects_inventory_affecting_fields(client, admin_access, posted_run):
    resp = client.patch(
        f"/api/v1/inventory/production/{posted_run['run_id']}",
        json={"quantity": "999", "screenType": "Should not apply"},
        headers={"Authorization": f"Bearer {admin_access}"},
    )
    assert resp.status_code == 400

    # The run is untouched - not even the field alongside the rejected one.
    fetched = client.get(f"/api/v1/inventory/production/{posted_run['run_id']}", headers={"Authorization": f"Bearer {admin_access}"})
    assert fetched.get_json()["screenType"] == "Original screen"


def test_update_production_missing_run_is_404(client, admin_access):
    resp = client.patch(
        f"/api/v1/inventory/production/{uuid.uuid4()}",
        json={"notes": "does not matter"},
        headers={"Authorization": f"Bearer {admin_access}"},
    )
    assert resp.status_code == 404
