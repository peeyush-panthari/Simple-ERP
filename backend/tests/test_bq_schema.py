"""Regression coverage for app/services/bq_schema.py's Postgres->BigQuery
type mapping. Runs against the real model metadata (pure introspection, no
live database needed) so a future model change that introduces an unmapped
type gets caught here instead of silently defaulting to STRING.
"""

from app.services.bq_schema import all_table_schemas


def test_every_table_maps_with_no_unmapped_types():
    schemas = all_table_schemas()
    assert len(schemas) > 60  # sanity: this should be ~72 tables, not a handful

    unmapped = [note for s in schemas for note in s.notes if "unmapped" in note]
    assert unmapped == [], f"unmapped SQLAlchemy type(s) found, mapper needs updating: {unmapped}"


def test_uuid_and_array_and_jsonb_columns_map_correctly():
    schemas = {s.name: s for s in all_table_schemas()}

    products = {f.name: f for f in schemas["products"].fields}
    assert products["id"].field_type == "STRING"
    assert products["id"].mode == "REQUIRED"
    assert products["alternate_uoms"].field_type == "STRING"
    assert products["alternate_uoms"].mode == "REPEATED"
    assert products["reorder_point"].field_type == "NUMERIC"
    assert products["reorder_point"].mode == "NULLABLE"
    assert products["published_at"].field_type == "TIMESTAMP"

    notifications = {f.name: f for f in schemas["notifications"].fields}
    assert notifications["data"].field_type == "JSON"
    assert notifications["recipients"].mode == "REPEATED"


def test_composite_primary_key_is_captured_and_used_for_clustering():
    schemas = {s.name: s for s in all_table_schemas()}
    party_types = schemas["party_types"]
    assert set(party_types.primary_key_columns) == {"tenant_id", "code"}
    assert party_types.cluster_by == ["tenant_id", "code"]


def test_table_without_tenant_id_clusters_on_its_own_primary_key():
    schemas = {s.name: s for s in all_table_schemas()}
    throttle = schemas["public_request_throttle"]
    assert "tenant_id" not in [f.name for f in throttle.fields]
    assert throttle.cluster_by == throttle.primary_key_columns


def test_identity_column_is_flagged_for_app_assigned_values():
    schemas = {s.name: s for s in all_table_schemas()}
    stock_ledger_notes = " ".join(schemas["stock_ledger"].notes)
    assert "seq" in stock_ledger_notes and "app-assigned" in stock_ledger_notes


def test_dropped_constraints_and_indexes_are_recorded_as_notes():
    schemas = {s.name: s for s in all_table_schemas()}
    products_notes = " ".join(schemas["products"].notes)
    assert "products_tenant_sku_uniq" in products_notes
    assert "BigQuery has no indexes" in products_notes
