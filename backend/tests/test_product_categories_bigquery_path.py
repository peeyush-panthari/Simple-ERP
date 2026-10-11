"""Coverage for the BigQuery write path added to product_categories.py under
Phase 4 of the migration plan (reference-data tier).

Mocks only run_write_transaction. Read-side validation (depth, cycle, code
collision, in-use) runs for real, since those are plain SELECTs unaffected by
which backend is live.
"""

import uuid
from unittest.mock import patch

import pytest

from app.core.errors import ProblemError
from tests.flaskcompat import db
from app.models.product_category import ProductCategory
from app.domains.foundation.masters_router import (
    CategoryBody,
    PatchCategoryBody,
    _create_category_bigquery,
    _delete_category_bigquery,
    _patch_category_bigquery,
)
from app.services.bq_writer import DeleteOp, InsertOp, UpdateOp


def _actor():
    return {"user_id": uuid.uuid4(), "email": "test@example.com"}


def _capture():
    captured = {}

    def fake(dataset, build_ops, **kwargs):
        captured["dataset"] = dataset
        captured["ops"] = build_ops()

    return captured, patch("app.domains.foundation.masters_router.run_write_transaction", side_effect=fake)


def _seed(tenant_id, code="SEED", **overrides) -> ProductCategory:
    row = ProductCategory(
        tenant_id=tenant_id, code=code, product_category="Seeded", product_types=[], **overrides
    )
    db.session.add(row)
    db.session.commit()
    return row


class TestCreateCategoryBigquery:
    def test_insert_carries_the_defaults_bigquery_will_not_supply(self, app, fresh_tenant_id):
        body = CategoryBody(code="WIDGETS", productCategory="Widgets", productTypes=["raw_material"])
        captured, patcher = _capture()

        with app.app_context(), patcher:
            result = _create_category_bigquery(fresh_tenant_id, _actor(), body)

        ops = captured["ops"]
        insert = next(o for o in ops if isinstance(o, InsertOp) and o.table == "product_categories")
        assert insert.values["tenant_id"] == fresh_tenant_id
        assert insert.values["code"] == "WIDGETS"
        assert insert.values["product_types"] == ["raw_material"]
        # server_default / onupdate are Postgres-side and never fire on BigQuery.
        assert insert.values["created_at"] is not None
        assert insert.values["updated_at"] == insert.values["created_at"]
        assert result["id"] == str(insert.values["id"])

    def test_audit_row_is_written_in_the_same_transaction(self, app, fresh_tenant_id):
        body = CategoryBody(code="AUDITED", productCategory="Audited")
        captured, patcher = _capture()

        with app.app_context(), patcher:
            _create_category_bigquery(fresh_tenant_id, _actor(), body)

        audit_op = next(o for o in captured["ops"] if isinstance(o, InsertOp) and o.table == "audit_log")
        assert audit_op.values["action"] == "product-category.created"
        assert audit_op.values["meta"] == {}

    def test_duplicate_code_is_rejected_since_the_unique_constraint_is_gone(self, app, fresh_tenant_id):
        """product_categories_tenant_code_uniq is dropped on BigQuery, so this
        SELECT is the only remaining guard."""
        captured, patcher = _capture()

        with app.app_context():
            _seed(fresh_tenant_id, code="TAKEN")
            body = CategoryBody(code="taken", productCategory="Case-insensitive clash")
            with patcher, pytest.raises(ProblemError) as excinfo:
                _create_category_bigquery(fresh_tenant_id, _actor(), body)

        assert excinfo.value.code == "CATEGORY_CODE_TAKEN"
        assert "ops" not in captured

    def test_unknown_parent_is_rejected_before_any_write(self, app, fresh_tenant_id):
        body = CategoryBody(code="ORPHAN", productCategory="Orphan", parentId=uuid.uuid4())
        captured, patcher = _capture()

        with app.app_context(), patcher, pytest.raises(ProblemError) as excinfo:
            _create_category_bigquery(fresh_tenant_id, _actor(), body)

        assert excinfo.value.status == 404
        assert "ops" not in captured


class TestPatchCategoryBigquery:
    def test_only_sent_fields_are_updated_and_updated_at_is_set_by_hand(self, app, fresh_tenant_id):
        captured, patcher = _capture()

        with app.app_context():
            row = _seed(fresh_tenant_id, code="BEFORE")
            with patcher:
                result = _patch_category_bigquery(
                    fresh_tenant_id, _actor(), row.id, PatchCategoryBody(productCategory="After")
                )

        update = next(o for o in captured["ops"] if isinstance(o, UpdateOp))
        assert update.set_values["product_category"] == "After"
        assert "code" not in update.set_values
        assert update.set_values["updated_at"] is not None, "onupdate=func.now() never fires on BigQuery"
        assert result["productCategory"] == "After"
        assert result["code"] == "BEFORE"

    def test_explicit_null_clears_a_nullable_field(self, app, fresh_tenant_id):
        """defaultTaxCode sent as null must be distinguishable from not sent."""
        captured, patcher = _capture()

        with app.app_context():
            row = _seed(fresh_tenant_id, code="CLEARME", default_tax_code="GST18")
            with patcher:
                result = _patch_category_bigquery(
                    fresh_tenant_id, _actor(), row.id, PatchCategoryBody(defaultTaxCode=None)
                )

        update = next(o for o in captured["ops"] if isinstance(o, UpdateOp))
        assert update.set_values["default_tax_code"] is None
        assert result["defaultTaxCode"] is None

    def test_an_empty_patch_still_audits_but_issues_no_update(self, app, fresh_tenant_id):
        """Matches the Postgres path, which audits before checking whether any
        field actually moved."""
        captured, patcher = _capture()

        with app.app_context():
            row = _seed(fresh_tenant_id, code="NOOP")
            with patcher:
                _patch_category_bigquery(fresh_tenant_id, _actor(), row.id, PatchCategoryBody())

        ops = captured["ops"]
        assert not [o for o in ops if isinstance(o, UpdateOp)]
        assert [o for o in ops if isinstance(o, InsertOp) and o.table == "audit_log"]

    def test_self_parenting_is_rejected(self, app, fresh_tenant_id):
        captured, patcher = _capture()

        with app.app_context():
            row = _seed(fresh_tenant_id, code="CYCLE")
            with patcher, pytest.raises(ProblemError) as excinfo:
                _patch_category_bigquery(
                    fresh_tenant_id, _actor(), row.id, PatchCategoryBody(parentId=row.id)
                )

        assert excinfo.value.code == "CATEGORY_CYCLE"
        assert "ops" not in captured


class TestDeleteCategoryBigquery:
    def test_audit_is_written_before_the_delete_in_one_transaction(self, app, fresh_tenant_id):
        captured, patcher = _capture()

        with app.app_context():
            row = _seed(fresh_tenant_id, code="GONE")
            with patcher:
                _delete_category_bigquery(fresh_tenant_id, _actor(), row.id)

        ops = captured["ops"]
        assert isinstance(ops[0], InsertOp) and ops[0].table == "audit_log"
        assert isinstance(ops[1], DeleteOp)
        assert ops[1].where == {"tenant_id": fresh_tenant_id, "id": row.id}

    def test_a_category_with_children_is_refused(self, app, fresh_tenant_id):
        """Postgres had ON DELETE RESTRICT behind this check; BigQuery enforces
        no foreign keys, so the check is the only guard left."""
        captured, patcher = _capture()

        with app.app_context():
            parent = _seed(fresh_tenant_id, code="PARENT")
            _seed(fresh_tenant_id, code="CHILD", parent_id=parent.id)
            with patcher, pytest.raises(ProblemError) as excinfo:
                _delete_category_bigquery(fresh_tenant_id, _actor(), parent.id)

        assert excinfo.value.code == "CATEGORY_IN_USE"
        assert "ops" not in captured

    def test_unknown_id_raises_not_found_before_any_write(self, app, fresh_tenant_id):
        captured, patcher = _capture()

        with app.app_context(), patcher, pytest.raises(ProblemError) as excinfo:
            _delete_category_bigquery(fresh_tenant_id, _actor(), uuid.uuid4())

        assert excinfo.value.status == 404
        assert "ops" not in captured
