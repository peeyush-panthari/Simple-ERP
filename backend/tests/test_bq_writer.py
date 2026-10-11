"""Unit coverage for app/services/bq_writer.py's SQL-script builder. Checks
the generated script text and parameter list directly - no live BigQuery
needed, since this validates our own string-building logic, not BigQuery's
actual execution behavior."""

import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.services.bq_writer import DeleteOp, InsertOp, Not, UpdateOp, build_write_script, run_write_transaction


class TestBuildWriteScriptInserts:
    def test_single_op_produces_one_insert_wrapped_in_a_transaction(self):
        op = InsertOp(table="business_entities", values={"id": "abc", "name": "Test Co"})
        sql, params = build_write_script("simple_erp_dev", [op])

        assert sql.startswith("BEGIN TRANSACTION;")
        assert sql.strip().endswith("COMMIT TRANSACTION;")
        assert "INSERT INTO `simple_erp_dev.business_entities` (id, name) VALUES (@p0_id, @p0_name);" in sql
        assert len(params) == 2
        assert {p.name for p in params} == {"p0_id", "p0_name"}

    def test_multiple_ops_get_distinctly_prefixed_params_even_with_shared_column_names(self):
        ops = [
            InsertOp(table="purchase_orders", values={"id": "po-1", "notes": "header note"}),
            InsertOp(table="po_lines", values={"id": "line-1", "notes": "line note"}),
        ]
        sql, params = build_write_script("simple_erp_dev", ops)

        assert "INSERT INTO `simple_erp_dev.purchase_orders` (id, notes) VALUES (@p0_id, @p0_notes);" in sql
        assert "INSERT INTO `simple_erp_dev.po_lines` (id, notes) VALUES (@p1_id, @p1_notes);" in sql
        param_names = {p.name for p in params}
        assert param_names == {"p0_id", "p0_notes", "p1_id", "p1_notes"}

    def test_empty_ops_list_raises(self):
        with pytest.raises(ValueError):
            build_write_script("simple_erp_dev", [])

    def test_uuid_is_bound_as_string(self):
        pid = uuid.uuid4()
        op = InsertOp(table="products", values={"id": pid})
        _, params = build_write_script("simple_erp_dev", [op])

        assert params[0].type_ == "STRING"
        assert params[0].value == str(pid)

    def test_decimal_is_bound_as_numeric(self):
        op = InsertOp(table="products", values={"reorder_point": Decimal("12.500000")})
        _, params = build_write_script("simple_erp_dev", [op])

        assert params[0].type_ == "NUMERIC"
        assert params[0].value == Decimal("12.500000")

    def test_date_is_bound_as_date(self):
        op = InsertOp(table="purchase_orders", values={"po_date": date(2026, 9, 6)})
        _, params = build_write_script("simple_erp_dev", [op])

        assert params[0].type_ == "DATE"
        assert params[0].value == date(2026, 9, 6)

    def test_none_is_bound_as_a_null_scalar_param(self):
        op = InsertOp(table="products", values={"description": None})
        _, params = build_write_script("simple_erp_dev", [op])

        assert params[0].value is None

    def test_list_is_bound_as_an_array_param(self):
        op = InsertOp(table="products", values={"alternate_uoms": ["KG", "G"]})
        _, params = build_write_script("simple_erp_dev", [op])

        assert params[0].array_type == "STRING"
        assert params[0].values == ["KG", "G"]

    def test_empty_list_is_bound_as_an_empty_array_param(self):
        op = InsertOp(table="products", values={"alternate_uoms": []})
        _, params = build_write_script("simple_erp_dev", [op])

        assert params[0].values == []

    def test_dict_is_bound_as_a_json_string(self):
        op = InsertOp(table="audit_log", values={"meta": {"number": "PO-1001"}})
        _, params = build_write_script("simple_erp_dev", [op])

        assert params[0].type_ == "JSON"
        assert params[0].value == '{"number": "PO-1001"}'


class TestBuildWriteScriptUpdates:
    def test_update_renders_set_and_equality_where(self):
        op = UpdateOp(table="business_entities", set_values={"is_default": False}, where={"tenant_id": "t1"})
        sql, params = build_write_script("simple_erp_dev", [op])

        assert "UPDATE `simple_erp_dev.business_entities` SET is_default = @p0_set_is_default WHERE tenant_id = @p0_where_tenant_id;" in sql
        param_names = {p.name for p in params}
        assert param_names == {"p0_set_is_default", "p0_where_tenant_id"}

    def test_not_wrapper_renders_not_equal_in_where(self):
        keep_id = uuid.uuid4()
        op = UpdateOp(table="business_entities", set_values={"is_default": False}, where={"tenant_id": "t1", "id": Not(keep_id)})
        sql, params = build_write_script("simple_erp_dev", [op])

        assert "id != @p0_where_id" in sql
        id_param = next(p for p in params if p.name == "p0_where_id")
        assert id_param.value == str(keep_id)

    def test_update_without_where_raises(self):
        op = UpdateOp(table="business_entities", set_values={"is_default": False}, where={})
        with pytest.raises(ValueError):
            build_write_script("simple_erp_dev", [op])

    def test_insert_and_update_can_share_one_script(self):
        """Matches the real 'unset other defaults' pattern: insert the new
        row, then update every other row's is_default flag, in one
        transaction."""
        new_id = uuid.uuid4()
        ops = [
            InsertOp(table="business_entities", values={"id": new_id, "is_default": True}),
            UpdateOp(table="business_entities", set_values={"is_default": False}, where={"tenant_id": "t1", "id": Not(new_id)}),
        ]
        sql, params = build_write_script("simple_erp_dev", ops)

        assert "INSERT INTO `simple_erp_dev.business_entities`" in sql
        assert "UPDATE `simple_erp_dev.business_entities`" in sql
        assert sql.index("INSERT") < sql.index("UPDATE")  # order preserved


class TestRunWriteTransaction:
    def test_calls_build_ops_fresh_on_every_retry(self):
        build_calls = []

        def build_ops():
            build_calls.append(1)
            return [InsertOp(table="doc_sequences", values={"attempt": len(build_calls)})]

        fake_result = object()
        fake_job = MagicMock(result=MagicMock(return_value=fake_result))
        from google.api_core.exceptions import Aborted

        fake_client = MagicMock(query=MagicMock(side_effect=[Aborted("conflict"), fake_job]))

        with patch("app.services.bq_transaction._get_client", return_value=fake_client), patch("time.sleep"):
            result = run_write_transaction("simple_erp_dev", build_ops, max_retries=5)

        assert result is fake_result
        assert len(build_calls) == 2  # rebuilt on the retry, not reused stale


class TestBuildWriteScriptDeletes:
    def test_delete_renders_a_parameterised_where(self):
        op = DeleteOp(table="product_categories", where={"tenant_id": "t-1", "id": "cat-1"})
        sql, params = build_write_script("simple_erp_dev", [op])

        assert (
            "DELETE FROM `simple_erp_dev.product_categories` "
            "WHERE tenant_id = @p0_where_tenant_id AND id = @p0_where_id;" in sql
        )
        assert {p.name for p in params} == {"p0_where_tenant_id", "p0_where_id"}

    def test_delete_honours_Not_the_same_way_update_does(self):
        op = DeleteOp(table="reservations", where={"order_id": "o-1", "status": Not("released")})
        sql, _ = build_write_script("simple_erp_dev", [op])

        assert "order_id = @p0_where_order_id" in sql
        assert "status != @p0_where_status" in sql

    def test_delete_without_a_where_is_refused(self):
        """An unconditional DELETE would empty the table; BigQuery has no
        transaction to roll it back from once committed."""
        with pytest.raises(ValueError, match="unconditional DELETE"):
            build_write_script("simple_erp_dev", [DeleteOp(table="products", where={})])

    def test_update_with_no_set_values_is_refused(self):
        """Would render `SET  WHERE ...`, which is a syntax error rather than
        the no-op the caller presumably intended."""
        with pytest.raises(ValueError, match="no SET values"):
            build_write_script("simple_erp_dev", [UpdateOp(table="products", set_values={}, where={"id": "p-1"})])

    def test_mixed_ops_keep_their_order_and_share_one_transaction(self):
        ops = [
            InsertOp(table="audit_log", values={"id": "a-1"}),
            UpdateOp(table="products", set_values={"status": "inactive"}, where={"id": "p-1"}),
            DeleteOp(table="product_specs", where={"product_id": "p-1"}),
        ]
        sql, _ = build_write_script("simple_erp_dev", ops)

        assert sql.count("BEGIN TRANSACTION;") == 1 and sql.count("COMMIT TRANSACTION;") == 1
        assert sql.index("INSERT INTO") < sql.index("UPDATE ") < sql.index("DELETE FROM")


class TestAuditInsertOp:
    def test_redacts_the_same_keys_audit_does(self):
        """The whole reason this helper exists: a hand-built audit row writes
        meta straight through and loses redaction."""
        from app.core.audit import audit_insert_op

        op = audit_insert_op(
            tenant_id=uuid.uuid4(),
            actor_id=uuid.uuid4(),
            actor_email="a@example.com",
            action="user.updated",
            entity_type="user",
            meta={"password": "hunter2", "email": "a@example.com"},
        )

        assert op.table == "audit_log"
        assert op.values["meta"] == {"password": "[REDACTED]", "email": "a@example.com"}

    def test_materialises_id_and_created_at_which_bigquery_will_not_default(self):
        from app.core.audit import audit_insert_op

        op = audit_insert_op(
            tenant_id=uuid.uuid4(), actor_id=None, actor_email=None, action="x.created", entity_type="x"
        )

        assert isinstance(op.values["id"], uuid.UUID)
        assert op.values["created_at"] is not None
        assert op.values["meta"] == {}  # audit()'s _redact(None) contract
