"""Derives BigQuery table schemas from the existing SQLAlchemy model metadata
(see /Users/Peeyush/.claude/plans/mossy-stirring-gosling.md, Phase 2).

This reads `Base.metadata` - pure Python introspection, no live database
connection needed - so it works today even without GCP access, and stays in
sync with the 68 models in app/models/ automatically instead of requiring a
hand-maintained parallel schema.

Type mapping (Postgres -> BigQuery), per the plan:
  UUID(as_uuid=True) / sa.Uuid          -> STRING
  JSON / JSONB                          -> JSON
  ARRAY(...)  (generic or postgresql)   -> REPEATED <item type>
  Numeric(p,s)                          -> NUMERIC (BigQuery NUMERIC is fixed 38,9 -
                                            fine for this codebase's Numeric(20,6)/(9,6))
  DateTime(timezone=True)               -> TIMESTAMP
  DateTime() (no tz)                    -> DATETIME
  Date                                  -> DATE
  Boolean                               -> BOOL
  Integer / BigInteger                  -> INT64
  String / Text                         -> STRING

Every CheckConstraint, ForeignKeyConstraint, UniqueConstraint, and Index is
dropped - BigQuery enforces none of them - and recorded in `notes` instead,
so the per-model app-level-validation audit called for in Phase 2 has a
concrete checklist to work from rather than needing to re-derive it by
re-reading all 68 files by hand.

PRIMARY KEY has no enforcement effect in BigQuery either; primary_key_columns
here is informational only (used to pick clustering keys), not a constraint
the created table will actually have.
"""

from __future__ import annotations

import dataclasses

import sqlalchemy as sa
from google.cloud import bigquery
from sqlalchemy.dialects import postgresql

from app.core.db import Base

_MAX_CLUSTERING_COLUMNS = 4
_SECOND_CLUSTER_KEY_CANDIDATES = ("id", "number", "code", "prefix")

# Tables verified (by diffing every frontend API call against every backend
# route) to have no path that populates them in the app as it actually runs
# today - shipping them to a fresh analytics warehouse would just be
# permanently-empty tables. Re-add any of these to the SQL rendering the day
# the frontend gains the workflow that writes to it.
OMITTED_TABLES: dict[str, str] = {
    "locations": "no 'create location' UI anywhere, and no seed data - the zone/aisle/rack/bin tree is never populated",
    "logistics_invoices": "backend route exists, logistics_state.py never calls POST or GET /logistics-invoices",
    "po_approval_records": "no approve/reject UI - procurement_state.py: a PO is issued immediately on creation",
    "po_revisions": "no amend UI - same module as po_approval_records",
    "product_aliases": "backend has full CRUD (/products/:id/aliases), product_state.py never calls it",
    "product_images": "backend has full CRUD (/products/:id/images), product_state.py never calls it",
    "product_specs": "backend has full CRUD (/products/:id/specs), product_state.py never calls it",
    "putaway_tasks": "POST /grns/:id/putaway is never called by the frontend, and would be unusable anyway (needs a location, and locations is empty)",
    "uom_conversions": "backend has full CRUD (/products/:id/conversions), product_state.py never calls it",
}

# GoogleSQL reserved keywords (cloud.google.com/bigquery/docs/reference/standard-sql/lexical#reserved_keywords)
# plus a couple of extra common SQL keywords ('key', 'trigger') quoted out of
# caution even though BigQuery itself doesn't reserve them.
_RESERVED_COLUMN_NAMES = {
    "all", "and", "any", "array", "as", "asc", "assert_rows_modified", "at",
    "between", "by", "case", "cast", "collate", "contains", "create", "cross",
    "cube", "current", "default", "define", "desc", "distinct", "else", "end",
    "enum", "escape", "except", "exclude", "exists", "extract", "false",
    "fetch", "following", "for", "from", "full", "group", "grouping",
    "groups", "hash", "having", "if", "ignore", "in", "inner", "intersect",
    "interval", "into", "is", "join", "lateral", "left", "like", "limit",
    "lookup", "merge", "natural", "new", "no", "not", "null", "nulls", "of",
    "on", "or", "order", "outer", "over", "partition", "preceding", "proto",
    "range", "recursive", "respect", "right", "rollup", "rows", "select",
    "set", "some", "struct", "tablesample", "then", "to", "treat", "true",
    "unbounded", "union", "unnest", "using", "when", "where", "window",
    "with", "within",
    "key", "trigger",
}


@dataclasses.dataclass
class TableSchema:
    name: str
    fields: list[bigquery.SchemaField]
    primary_key_columns: list[str]  # informational only - not enforced by BigQuery
    cluster_by: list[str]
    notes: list[str]


def _map_scalar_type(t: sa.types.TypeEngine) -> tuple[str, list[str]]:
    """Maps one column's (non-array) SQLAlchemy type to a BigQuery type name."""
    if isinstance(t, (postgresql.UUID, sa.Uuid)):
        return "STRING", []
    if isinstance(t, sa.JSON):  # covers postgresql.JSON and JSONB - same base class
        return "JSON", []
    if isinstance(t, sa.Numeric):
        return "NUMERIC", []
    if isinstance(t, sa.Date) and not isinstance(t, sa.DateTime):
        return "DATE", []
    if isinstance(t, sa.DateTime):
        return ("TIMESTAMP" if getattr(t, "timezone", False) else "DATETIME"), []
    if isinstance(t, sa.Boolean):
        return "BOOL", []
    if isinstance(t, (sa.BigInteger, sa.Integer)):
        return "INT64", []
    if isinstance(t, (sa.String, sa.Text)):
        return "STRING", []
    return "STRING", [f"unmapped SQLAlchemy type {type(t).__name__}, defaulted to STRING - verify by hand"]


def _column_to_field(column: sa.Column) -> tuple[bigquery.SchemaField, list[str]]:
    notes: list[str] = []
    if isinstance(column.type, sa.ARRAY):
        item_type, item_notes = _map_scalar_type(column.type.item_type)
        notes.extend(item_notes)
        return bigquery.SchemaField(column.name, item_type, mode="REPEATED"), notes

    bq_type, type_notes = _map_scalar_type(column.type)
    notes.extend(type_notes)
    mode = "NULLABLE" if column.nullable else "REQUIRED"
    if column.identity is not None:
        notes.append("Postgres IDENTITY column - value must be app-assigned (app.services.sequences) instead of DB auto-increment")
    return bigquery.SchemaField(column.name, bq_type, mode=mode), notes


def _dropped_constraint_notes(table: sa.Table) -> list[str]:
    notes = []
    for constraint in table.constraints:
        if isinstance(constraint, sa.PrimaryKeyConstraint):
            continue  # handled separately as informational primary_key_columns
        label = constraint.name or type(constraint).__name__
        notes.append(f"dropped {type(constraint).__name__} '{label}' - not enforced by BigQuery, needs app-level check if it was the only guard")
    for index in table.indexes:
        notes.append(f"dropped Index '{index.name}' - BigQuery has no indexes")
    return notes


def _cluster_by_for(table: sa.Table) -> list[str]:
    columns = table.columns.keys()
    cluster_by: list[str] = []
    if "tenant_id" in columns:
        cluster_by.append("tenant_id")
        for candidate in _SECOND_CLUSTER_KEY_CANDIDATES:
            if candidate in columns and candidate not in cluster_by:
                cluster_by.append(candidate)
                break
    else:
        # No tenant_id (a handful of platform-wide tables, e.g.
        # public_request_throttle) - cluster on the table's own primary key
        # instead of leaving it unclustered.
        cluster_by.extend(c.name for c in table.columns if c.primary_key)
    return cluster_by[:_MAX_CLUSTERING_COLUMNS]


def table_schema_for(table: sa.Table) -> TableSchema:
    fields: list[bigquery.SchemaField] = []
    notes: list[str] = []
    for column in table.columns:
        field, column_notes = _column_to_field(column)
        fields.append(field)
        notes.extend(f"{column.name}: {n}" for n in column_notes)
    notes.extend(_dropped_constraint_notes(table))
    pk_columns = [c.name for c in table.columns if c.primary_key]
    return TableSchema(
        name=table.name,
        fields=fields,
        primary_key_columns=pk_columns,
        cluster_by=_cluster_by_for(table),
        notes=notes,
    )


def all_table_schemas() -> list[TableSchema]:
    """One TableSchema per model, in dependency order (parents before
    children per SQLAlchemy's sorted_tables - purely informational for
    BigQuery since there's no FK enforcement, but keeps CREATE TABLE output
    in a sane, readable order)."""
    import app.models  # noqa: F401 - populates Base.metadata as a side effect

    return [table_schema_for(t) for t in Base.metadata.sorted_tables]


def create_dataset(client: "bigquery.Client", project: str, dataset: str, location: str) -> "bigquery.DatasetReference":
    """Idempotent CREATE SCHEMA (dataset) IF NOT EXISTS. Shared by
    scripts/bq_schema_sync.py (the real dev/prod dataset) and
    tests/conftest.py (a throwaway per-session test dataset, Phase 5)."""
    dataset_ref = bigquery.DatasetReference(project, dataset)
    ds = bigquery.Dataset(dataset_ref)
    ds.location = location
    client.create_dataset(ds, exists_ok=True)
    return dataset_ref


def create_tables(client: "bigquery.Client", dataset_ref: "bigquery.DatasetReference", schemas: list[TableSchema] | None = None) -> list[str]:
    """Idempotent CREATE TABLE IF NOT EXISTS for every schema (all 72 models
    by default). Returns the full_table_id of each table created/confirmed."""
    schemas = schemas if schemas is not None else all_table_schemas()
    created = []
    for s in schemas:
        table = bigquery.Table(dataset_ref.table(s.name), schema=s.fields)
        if s.cluster_by:
            table.clustering_fields = s.cluster_by
        result = client.create_table(table, exists_ok=True)
        created.append(result.full_table_id)
    return created


def drop_dataset(client: "bigquery.Client", project: str, dataset: str) -> None:
    """Deletes a dataset and every table in it. Used to tear down the
    throwaway per-session test dataset (Phase 5) - never call this on a real
    dev/prod dataset."""
    client.delete_dataset(bigquery.DatasetReference(project, dataset), delete_contents=True, not_found_ok=True)


def _quote_column(name: str) -> str:
    return f"`{name}`" if name.lower() in _RESERVED_COLUMN_NAMES else name


def _field_sql(field: "bigquery.SchemaField") -> str:
    type_sql = f"ARRAY<{field.field_type}>" if field.mode == "REPEATED" else field.field_type
    suffix = " NOT NULL" if field.mode == "REQUIRED" else ""
    return f"  {_quote_column(field.name)} {type_sql}{suffix}"


def render_sql(schemas: list[TableSchema], *, project: str, dataset: str, location: str) -> str:
    """Renders `schemas` as the plain-SQL DDL checked in at
    bigquery/schema.sql, for human review / manual `bq query` use outside
    the app. Drops every table in OMITTED_TABLES (see its docstring)."""
    included = [s for s in schemas if s.name not in OMITTED_TABLES]

    omitted_lines = "\n".join(f"--   - {name}: {reason}" for name, reason in sorted(OMITTED_TABLES.items()))
    header = f"""-- =====================================================================
-- Simple ERP -- BigQuery schema (generated)
-- =====================================================================
-- Source of truth: app/services/bq_schema.py, which introspects
-- Base.metadata (the SQLAlchemy models in app/models/) at import time.
-- This file is a plain-SQL rendering of exactly what
-- `python scripts/bq_schema_sync.py --sql` reports right now, for
-- review/manual `bq query` use outside the app. It is NOT hand-maintained
-- - regenerate it (or just run bq_schema_sync.py directly against a real
-- GCP project) whenever a model changes, rather than hand-editing this.
--
-- Project : {project}  (placeholder - see app/config.py:gcp_project_id)
-- Dataset : {dataset}
-- Location: {location}
--
-- Every CheckConstraint / ForeignKeyConstraint / UniqueConstraint / Index
-- from the Postgres models is dropped (BigQuery enforces none of them) and
-- listed as a comment under its table instead, per Phase 2 of the plan at
-- /Users/Peeyush/.claude/plans/mossy-stirring-gosling.md -- each one is a
-- candidate for an app-level check if it was the only guard.
--
-- {len(OMITTED_TABLES)} tables from the Postgres model set are DELIBERATELY OMITTED
-- below: verified (by diffing every frontend API call against every
-- backend route) to have no path that populates them in the app as it
-- actually runs today - shipping them to a fresh analytics warehouse would
-- just be permanently-empty tables. Re-add any of these the day the
-- frontend gains the workflow that writes to it:
{omitted_lines}
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS `{project}.{dataset}`
OPTIONS (location = "{location}");"""

    parts = [header]
    for s in included:
        table_lines = [f"-- ---- {s.name} ({len(s.fields)} columns) ----"]
        table_lines.extend(f"-- {note}" for note in s.notes)
        table_lines.append(f"CREATE TABLE IF NOT EXISTS `{project}.{dataset}.{s.name}` (")
        table_lines.append(",\n".join(_field_sql(f) for f in s.fields))
        table_lines.append(")")
        cluster = ", ".join(s.cluster_by) if s.cluster_by else None
        table_lines.append(f"CLUSTER BY {cluster};" if cluster else ";")
        parts.append("\n".join(table_lines))

    return "\n\n".join(parts) + "\n"
