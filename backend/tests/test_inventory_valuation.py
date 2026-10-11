"""GET /inventory/average-costs - unlike /inventory/valuation, this must
resolve a product's cost regardless of which StockBalance bucket its
quantity currently sits in (a product with stock only in quarantine, not
available, still has an average cost - just no `lines` entry under
compute_valuation(bucket='available')). Backs Stock Balances' Cost/Count
toggle, which needs a SKU's cost applied to every bucket column shown."""

import uuid

import pytest

from tests.flaskcompat import db as _db
from app.services import inventory_ledger
from app.services.inventory_ledger import LedgerPosting


@pytest.fixture
def product_and_warehouse(app, default_tenant_id):
    from app.models.product import Product
    from app.models.warehouse import Warehouse

    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        product = Product(tenant_id=default_tenant_id, sku=f"TST-VAL-{suffix}", name="Valuation Test Product", type="raw_material", uom="KG")
        warehouse = Warehouse(tenant_id=default_tenant_id, code=f"WH-VAL-{suffix}", name="Valuation Test Warehouse", status="active")
        _db.session.add_all([product, warehouse])
        _db.session.commit()
        ids = {"tenant_id": default_tenant_id, "product_id": product.id, "sku": product.sku, "warehouse_id": warehouse.id}
        yield ids

        from app.models.stock_balance import StockBalance
        from app.models.stock_ledger import StockLedger

        for model in (StockLedger, StockBalance):
            model.query.filter_by(product_id=ids["product_id"]).delete(synchronize_session=False)
        Product.query.filter_by(id=ids["product_id"]).delete(synchronize_session=False)
        Warehouse.query.filter_by(id=ids["warehouse_id"]).delete(synchronize_session=False)
        _db.session.commit()


@pytest.fixture
def admin_access(client, fresh_admin):
    resp = client.post("/api/v1/auth/login", json={"email": fresh_admin["email"], "password": fresh_admin["password"]})
    return resp.get_json()["accessToken"]


def test_average_costs_resolves_a_product_with_stock_only_in_a_non_default_bucket(app, client, admin_access, product_and_warehouse):
    ctx = product_and_warehouse
    with app.app_context():
        inventory_ledger.post(
            LedgerPosting(
                tenant_id=ctx["tenant_id"],
                product_id=ctx["product_id"],
                sku=ctx["sku"],
                warehouse_id=ctx["warehouse_id"],
                quantity="10",
                uom="KG",
                bucket="quarantine",
                movement_type="receipt",
                reference_type="test-fixture",
                reference_id="fixture-1",
                unit_cost="42",
            )
        )
        _db.session.commit()

    headers = {"Authorization": f"Bearer {admin_access}"}

    # The general valuation endpoint, scoped to 'available', has nothing to
    # say about this product - it has no available-bucket stock at all.
    val_resp = client.get("/api/v1/inventory/valuation", query_string={"bucket": "available"}, headers=headers)
    assert val_resp.status_code == 200
    assert not any(l["productId"] == str(ctx["product_id"]) for l in val_resp.get_json()["lines"])

    # average-costs finds it anyway, from its quarantine-bucket receipt.
    resp = client.get("/api/v1/inventory/average-costs", headers=headers)
    assert resp.status_code == 200
    row = next(r for r in resp.get_json()["data"] if r["productId"] == str(ctx["product_id"]))
    assert row["averageCost"] == "42.000000"
