"""Coverage for the BigQuery write path added to party_types.py under Phase 4
of the migration plan (reference-data tier).

Mocks only run_write_transaction - the actual BigQuery network call. The
read-side checks (duplicate code, row lookup) run for real against whatever
db_backend is configured, since those are plain SELECTs unaffected by which
backend is live. This validates op construction and the response body without
needing a real BigQuery dataset.
"""

import uuid
from unittest.mock import patch

import pytest

from app.core.errors import ProblemError
from app.models.party_type import PartyType
from app.domains.foundation.router import (
    CreatePartyTypeBody,
    PatchPartyTypeBody,
    _create_party_type_bigquery,
    _patch_party_type_bigquery,
)
from app.services.bq_writer import InsertOp, UpdateOp


def _capture(monkeypatch_target: str):
    """Patches run_write_transaction in the route module and records the ops
    each attempt would have written."""
    captured = {}

    def fake(dataset, build_ops, **kwargs):
        captured["dataset"] = dataset
        captured["ops"] = build_ops()

    return captured, patch(monkeypatch_target, side_effect=fake)


class TestCreatePartyTypeBigquery:
    def test_builds_one_insert_with_the_defaults_the_model_would_have_supplied(self, app):
        tenant_id = uuid.uuid4()
        body = CreatePartyTypeBody(label="Contract Manufacturer", baseType="vendor")
        captured, patcher = _capture("app.domains.foundation.router.run_write_transaction")

        with app.app_context(), patcher:
            result = _create_party_type_bigquery(tenant_id, body)

        ops = captured["ops"]
        assert len(ops) == 1 and isinstance(ops[0], InsertOp)
        values = ops[0].values
        assert ops[0].table == "party_types"
        assert values["tenant_id"] == tenant_id
        assert values["code"] == "contract_manufacturer"  # slugged from the label
        assert values["base_type"] == "vendor"
        # BigQuery has no Python-side default and no server_default, so both
        # have to be materialised into the INSERT by hand.
        assert values["status"] == "active"
        assert values["created_at"] is not None

        assert result["code"] == "contract_manufacturer"
        assert result["status"] == "active"
        assert result["createdAt"] == values["created_at"].isoformat()

    def test_explicit_code_is_slugged_not_taken_verbatim(self, app):
        body = CreatePartyTypeBody(label="Anything", baseType="both", code="Job Worker!!")
        captured, patcher = _capture("app.domains.foundation.router.run_write_transaction")

        with app.app_context(), patcher:
            _create_party_type_bigquery(uuid.uuid4(), body)

        assert captured["ops"][0].values["code"] == "job_worker"

    def test_a_code_that_slugs_to_nothing_is_rejected_before_any_write(self, app):
        body = CreatePartyTypeBody(label="Vendor", baseType="vendor", code="!!!")
        captured, patcher = _capture("app.domains.foundation.router.run_write_transaction")

        with app.app_context(), patcher, pytest.raises(ProblemError) as excinfo:
            _create_party_type_bigquery(uuid.uuid4(), body)

        assert excinfo.value.code == "PARTY_TYPE_CODE_INVALID"
        assert "ops" not in captured

    def test_duplicate_code_is_caught_by_the_app_since_bigquery_enforces_no_key(self, app, fresh_tenant_id):
        """(tenant_id, code) is a composite PK in Postgres and nothing at all
        in BigQuery, so this SELECT is the only remaining guard."""
        body = CreatePartyTypeBody(label="Duplicate Me", baseType="customer")
        captured, patcher = _capture("app.domains.foundation.router.run_write_transaction")

        with app.app_context():
            from tests.flaskcompat import db

            db.session.add(
                PartyType(tenant_id=fresh_tenant_id, code="duplicate_me", label="Existing", base_type="vendor")
            )
            db.session.commit()

            with patcher, pytest.raises(ProblemError) as excinfo:
                _create_party_type_bigquery(fresh_tenant_id, body)

        assert excinfo.value.code == "PARTY_TYPE_TAKEN"
        assert "ops" not in captured


class TestPatchPartyTypeBigquery:
    def test_updates_only_the_fields_that_were_sent(self, app, fresh_tenant_id):
        captured, patcher = _capture("app.domains.foundation.router.run_write_transaction")

        with app.app_context():
            from tests.flaskcompat import db

            db.session.add(
                PartyType(tenant_id=fresh_tenant_id, code="patch_me", label="Before", base_type="vendor")
            )
            db.session.commit()

            with patcher:
                result = _patch_party_type_bigquery(fresh_tenant_id, "patch_me", PatchPartyTypeBody(label="After"))

        ops = captured["ops"]
        assert len(ops) == 1 and isinstance(ops[0], UpdateOp)
        assert ops[0].set_values == {"label": "After"}
        assert ops[0].where == {"tenant_id": fresh_tenant_id, "code": "patch_me"}
        assert result["label"] == "After"
        assert result["baseType"] == "vendor"  # untouched fields come from the read

    def test_an_empty_patch_writes_nothing_and_returns_the_row_unchanged(self, app, fresh_tenant_id):
        """Matches the Postgres path, which commits a no-op. An UpdateOp with
        no set_values would render invalid SQL, so it must not be built."""
        captured, patcher = _capture("app.domains.foundation.router.run_write_transaction")

        with app.app_context():
            from tests.flaskcompat import db

            db.session.add(
                PartyType(tenant_id=fresh_tenant_id, code="untouched", label="Same", base_type="both")
            )
            db.session.commit()

            with patcher:
                result = _patch_party_type_bigquery(fresh_tenant_id, "untouched", PatchPartyTypeBody())

        assert "ops" not in captured, "no BigQuery job should be issued for an empty patch"
        assert result["label"] == "Same"

    def test_unknown_code_raises_not_found_before_any_write(self, app, fresh_tenant_id):
        captured, patcher = _capture("app.domains.foundation.router.run_write_transaction")

        with app.app_context(), patcher, pytest.raises(ProblemError) as excinfo:
            _patch_party_type_bigquery(fresh_tenant_id, "does-not-exist", PatchPartyTypeBody(label="xx"))

        assert excinfo.value.status == 404
        assert "ops" not in captured
