"""Coverage for the BigQuery write path added to business_entities.py under
Phase 4 of the migration plan (the first module ported). Mocks only
run_write_transaction (the actual BigQuery network call) - the read-side
checks (code collision, is-first) run for real against whatever db_backend
is actually configured, since those are plain SELECTs unaffected by which
backend is live. This validates the ops/response-construction logic without
needing a real BigQuery dataset.
"""

import uuid
from unittest.mock import patch

from app.domains.foundation.masters_router import BusinessEntityBody, _create_business_entity_bigquery
from app.services.bq_writer import InsertOp, Not, UpdateOp


def _actor():
    return {"user_id": uuid.uuid4(), "email": "test@example.com"}


class TestCreateBusinessEntityBigquery:
    def test_first_entity_for_a_fresh_tenant_becomes_default(self, app):
        tenant_id = uuid.uuid4()  # fresh tenant with zero existing entities
        body = BusinessEntityBody(name="Acme Corp", city="Pune", stateCode="27")

        captured_ops = {}

        def fake_run_write_transaction(dataset, build_ops, **kwargs):
            captured_ops["ops"] = build_ops()
            captured_ops["dataset"] = dataset

        with app.app_context(), patch("app.domains.foundation.masters_router.run_write_transaction", side_effect=fake_run_write_transaction):
            result = _create_business_entity_bigquery(tenant_id, _actor(), body)

        assert result["name"] == "Acme Corp"
        assert result["isDefault"] is True  # first entity for the tenant

        ops = captured_ops["ops"]
        insert_ops = [o for o in ops if isinstance(o, InsertOp)]
        update_ops = [o for o in ops if isinstance(o, UpdateOp)]

        entity_insert = next(o for o in insert_ops if o.table == "business_entities")
        assert entity_insert.values["is_default"] is True
        assert entity_insert.values["tenant_id"] == tenant_id

        audit_insert = next(o for o in insert_ops if o.table == "audit_log")
        assert audit_insert.values["action"] == "business-entity.created"

        # Matches the Postgres path's behavior exactly: _unset_other_defaults
        # runs whenever make_default is true, even for the first entity where
        # there's nothing else to unset (a harmless no-op UPDATE, not a bug).
        assert len(update_ops) == 1
        assert update_ops[0].where["tenant_id"] == tenant_id

    def test_explicit_default_unsets_other_rows_in_the_same_tenant(self, app):
        tenant_id = uuid.uuid4()
        body = BusinessEntityBody(name="Second Entity", city="Pune", stateCode="27", isDefault=True)

        captured_ops = {}

        def fake_run_write_transaction(dataset, build_ops, **kwargs):
            captured_ops["ops"] = build_ops()

        # Simulate a tenant that already has an entity (is_first would be False)
        # by patching the count() call the read-side check makes.
        with app.app_context(), patch("app.domains.foundation.masters_router.BusinessEntity.query") as mock_query, patch(
            "app.domains.foundation.masters_router.run_write_transaction", side_effect=fake_run_write_transaction
        ):
            mock_query.filter.return_value.first.return_value = None  # no code collision
            mock_query.filter_by.return_value.count.return_value = 1  # not the first entity

            result = _create_business_entity_bigquery(tenant_id, _actor(), body)

        assert result["isDefault"] is True
        ops = captured_ops["ops"]
        update_ops = [o for o in ops if isinstance(o, UpdateOp)]
        assert len(update_ops) == 1
        assert update_ops[0].set_values == {"is_default": False}
        assert update_ops[0].where["tenant_id"] == tenant_id
        assert isinstance(update_ops[0].where["id"], Not)

    def test_non_default_entity_for_an_existing_tenant_does_not_touch_other_rows(self, app):
        tenant_id = uuid.uuid4()
        body = BusinessEntityBody(name="Third Entity", city="Pune", stateCode="27", isDefault=False)

        captured_ops = {}

        def fake_run_write_transaction(dataset, build_ops, **kwargs):
            captured_ops["ops"] = build_ops()

        with app.app_context(), patch("app.domains.foundation.masters_router.BusinessEntity.query") as mock_query, patch(
            "app.domains.foundation.masters_router.run_write_transaction", side_effect=fake_run_write_transaction
        ):
            mock_query.filter.return_value.first.return_value = None
            mock_query.filter_by.return_value.count.return_value = 1  # not the first entity

            result = _create_business_entity_bigquery(tenant_id, _actor(), body)

        assert result["isDefault"] is False
        ops = captured_ops["ops"]
        assert [o for o in ops if isinstance(o, UpdateOp)] == []
