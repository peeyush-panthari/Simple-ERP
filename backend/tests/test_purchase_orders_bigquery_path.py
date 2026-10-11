"""Coverage for the BigQuery write path added to purchase_orders.py under
Phase 4 of the migration plan - the representative "multi-table insert with
a sequence number" module (PO header + N lines + audit row), covering the
shape most of this codebase's write sites follow. Mocks only
run_write_transaction (the actual BigQuery network call); _validate_po and
_compute_gst_split run for real against whatever db_backend is actually
configured, since those are plain reads/computation unaffected by which
backend is live.
"""

import uuid
from datetime import date

from app.models.party import Party
from app.models.product import Product
from app.models.warehouse import Warehouse
from app.domains.procurement.router import LineBody, PoBody, _CreatedPoRef, _create_po_bigquery
from app.services.bq_writer import InsertOp
from unittest.mock import patch

from tests.test_purchase_orders import _setup
from tests.test_logistics_finance import _auth_headers


def _actor():
    return {"user_id": uuid.uuid4(), "email": "test@example.com"}


DEFAULT_TENANT = uuid.UUID("00000000-0000-4000-8000-000000000001")


class TestCreatePoBigquery:
    def test_builds_header_line_and_audit_inserts(self, app, client, fresh_admin):
        # Seeds its own vendor/warehouse/product - the suite runs on an empty test database.
        headers = _auth_headers(client, fresh_admin)
        _vendor, _warehouse, _product = _setup(client, headers)
        with app.app_context():
            vendor = Party.query.get(uuid.UUID(_vendor["id"]))
            warehouse = Warehouse.query.get(uuid.UUID(_warehouse["id"]))
            product = Product.query.get(uuid.UUID(_product["id"]))
            assert vendor.status == "active" and warehouse.status == "active" and product.purchasable and product.status == "active"

            body = PoBody(
                vendorId=vendor.id,
                warehouseId=warehouse.id,
                expectedDate=date(2026, 10, 1),
                lines=[LineBody(productId=product.id, quantity="2", uom=product.uom, unitPrice="100", taxCode="GST18")],
            )

            captured = {}

            def fake_run_write_transaction(dataset, build_ops, **kwargs):
                captured["ops"] = build_ops()
                captured["dataset"] = dataset

            with patch("app.domains.procurement.router.run_write_transaction", side_effect=fake_run_write_transaction):
                result = _create_po_bigquery(DEFAULT_TENANT, _actor(), body)

            assert isinstance(result, _CreatedPoRef)
            assert result.number.startswith("PO-")

            ops = captured["ops"]
            assert all(isinstance(o, InsertOp) for o in ops)

            po_insert = next(o for o in ops if o.table == "purchase_orders")
            assert po_insert.values["id"] == result.id
            assert po_insert.values["status"] == "issued"
            assert float(po_insert.values["total"]) == 236.0  # 2*100 subtotal + 18% GST = 236, matches the live Postgres smoke test

            line_inserts = [o for o in ops if o.table == "po_lines"]
            assert len(line_inserts) == 1
            assert line_inserts[0].values["po_id"] == result.id
            assert line_inserts[0].values["line_no"] == 1
            assert line_inserts[0].values["sku"] == product.sku

            audit_insert = next(o for o in ops if o.table == "audit_log")
            assert audit_insert.values["action"] == "po.created"
            assert audit_insert.values["entity_id"] == str(result.id)

            # Ops are ordered header -> lines -> audit, matching the Postgres path's commit order.
            assert [o.table for o in ops] == ["purchase_orders"] + ["po_lines"] * len(line_inserts) + ["audit_log"]

    def test_multiple_lines_get_sequential_line_numbers(self, app, client, fresh_admin):
        headers = _auth_headers(client, fresh_admin)
        _vendor, _warehouse, _p1 = _setup(client, headers)
        _p2 = _setup(client, headers)[2]
        with app.app_context():
            vendor = Party.query.get(uuid.UUID(_vendor["id"]))
            warehouse = Warehouse.query.get(uuid.UUID(_warehouse["id"]))
            products = [Product.query.get(uuid.UUID(p["id"])) for p in (_p1, _p2)]

            body = PoBody(
                vendorId=vendor.id,
                warehouseId=warehouse.id,
                expectedDate=date(2026, 10, 1),
                lines=[
                    LineBody(productId=products[0].id, quantity="1", uom=products[0].uom, unitPrice="50", taxCode="GST0"),
                    LineBody(productId=products[1].id, quantity="3", uom=products[1].uom, unitPrice="20", taxCode="GST0"),
                ],
            )

            captured = {}

            def fake_run_write_transaction(dataset, build_ops, **kwargs):
                captured["ops"] = build_ops()

            with patch("app.domains.procurement.router.run_write_transaction", side_effect=fake_run_write_transaction):
                _create_po_bigquery(DEFAULT_TENANT, _actor(), body)

            line_inserts = [o for o in captured["ops"] if o.table == "po_lines"]
            assert [o.values["line_no"] for o in line_inserts] == [1, 2]
