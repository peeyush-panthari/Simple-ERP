"""New coverage - the Node inventory service had no tests for db/ledger.ts.
Exercises post()'s idempotency guarantee and the balance projection against
the real dev database (matching this project's DB-backed test convention)."""

import uuid

import pytest

from tests.flaskcompat import db as _db
from app.services import inventory_ledger
from app.services.inventory_ledger import LedgerPosting
from app.core.money import decimal_str


@pytest.fixture
def product_and_warehouse(app, default_tenant_id):
    """A throwaway product+warehouse pair scoped to this test, isolated by a
    unique SKU/code suffix (repeated pytest runs share the same dev DB)."""
    from app.models.product import Product
    from app.models.warehouse import Warehouse

    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        product = Product(tenant_id=default_tenant_id, sku=f"TST-LEDGER-{suffix}", name="Ledger Test Product", type="raw_material", uom="KG")
        warehouse = Warehouse(tenant_id=default_tenant_id, code=f"WH-TST-{suffix}", name="Ledger Test Warehouse", status="active")
        _db.session.add_all([product, warehouse])
        _db.session.commit()
        product_id, warehouse_id = product.id, warehouse.id
        yield {"tenant_id": default_tenant_id, "product_id": product_id, "sku": product.sku, "warehouse_id": warehouse_id}

        # This fixture writes into the SHARED default tenant, so clean up by
        # this product/warehouse only - never by tenant_id. Without it every
        # run left a product, a warehouse and its ledger rows behind.
        from app.models.stock_balance import StockBalance
        from app.models.stock_ledger import StockLedger

        for model in (StockLedger, StockBalance):
            model.query.filter_by(product_id=product_id).delete(synchronize_session=False)
        Product.query.filter_by(id=product_id).delete(synchronize_session=False)
        Warehouse.query.filter_by(id=warehouse_id).delete(synchronize_session=False)
        _db.session.commit()


def test_post_is_idempotent_on_reference_movement_product_batch_location(app, product_and_warehouse):
    ctx = product_and_warehouse
    with app.app_context():
        entry = LedgerPosting(
            tenant_id=ctx["tenant_id"],
            product_id=ctx["product_id"],
            sku=ctx["sku"],
            warehouse_id=ctx["warehouse_id"],
            quantity="10",
            uom="KG",
            bucket="available",
            movement_type="receipt",
            reference_type="test",
            reference_id="ref-1",
        )
        first = inventory_ledger.post(entry)
        assert first is not None

        second = inventory_ledger.post(entry)
        assert second is None  # redelivered/retried posting inserts nothing

        _db.session.commit()

        totals = inventory_ledger.bucket_totals(ctx["tenant_id"], ctx["product_id"], ctx["warehouse_id"])
        assert totals["available"] == "10.000000"  # not double-counted


def test_post_folds_multiple_distinct_postings_into_the_balance(app, product_and_warehouse):
    ctx = product_and_warehouse
    with app.app_context():
        base = dict(tenant_id=ctx["tenant_id"], product_id=ctx["product_id"], sku=ctx["sku"], warehouse_id=ctx["warehouse_id"], uom="KG", bucket="available", movement_type="receipt", reference_type="test")
        inventory_ledger.post(LedgerPosting(reference_id="ref-a", quantity="5", **base))
        inventory_ledger.post(LedgerPosting(reference_id="ref-b", quantity="7", **base))
        _db.session.commit()

        totals = inventory_ledger.bucket_totals(ctx["tenant_id"], ctx["product_id"], ctx["warehouse_id"])
        assert totals["available"] == "12.000000"


def test_reverse_posts_a_cancelling_entry_not_a_delete(app, product_and_warehouse):
    ctx = product_and_warehouse
    with app.app_context():
        original = LedgerPosting(
            tenant_id=ctx["tenant_id"],
            product_id=ctx["product_id"],
            sku=ctx["sku"],
            warehouse_id=ctx["warehouse_id"],
            quantity="20",
            uom="KG",
            bucket="available",
            movement_type="adjustment",
            reference_type="test",
            reference_id="ref-rev",
        )
        posted = inventory_ledger.post(original)
        reversal = inventory_ledger.reverse(original, original_id=posted["id"], reason="test reversal", actor_id=None)
        assert reversal is not None
        _db.session.commit()

        totals = inventory_ledger.bucket_totals(ctx["tenant_id"], ctx["product_id"], ctx["warehouse_id"])
        assert totals["available"] == "0.000000"

        from app.models.stock_ledger import StockLedger

        rows = StockLedger.query.filter_by(tenant_id=ctx["tenant_id"], product_id=ctx["product_id"]).all()
        assert len(rows) == 2  # append-only: both the original and the reversal exist


def test_draw_from_splits_across_sources_and_returns_location_less_residue():
    from app.services.inventory_ledger import SourceBalance, draw_from

    sources = [
        SourceBalance(location_id="loc-1", batch_no="B1", expiry_date=None, quantity="4", uom="KG"),
        SourceBalance(location_id="loc-2", batch_no="B2", expiry_date=None, quantity="3", uom="KG"),
    ]
    draws = draw_from(sources, "10")
    assert [decimal_str(d.quantity) for d in draws] == ["4.000000", "3.000000", "3.000000"]
    assert draws[-1].source is None  # residue beyond what the sources hold
