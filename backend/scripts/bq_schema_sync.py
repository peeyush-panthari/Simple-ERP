"""Creates (or confirms) every BigQuery table for this app's schema, derived
from app/services/bq_schema.py (which introspects the existing SQLAlchemy
models - see /Users/Peeyush/.claude/plans/mossy-stirring-gosling.md, Phase 2).

This replaces Alembic for the BigQuery backend: Alembic's autogenerate
diffing has no meaningful support for a constraint-free, index-free schema,
so this is a small idempotent CREATE-TABLE-IF-NOT-EXISTS sync instead of a
migration-history tool. Fresh tables only for now (per the user's own
confirmation) - it does not yet diff/ALTER an existing table's columns; add
that once there's a real second-schema-version to test it against.

Usage:
    # Safe to run right now, with no GCP access at all - prints what would
    # be created without touching anything:
    .venv/bin/python scripts/bq_schema_sync.py --dry-run

    # Regenerates bigquery/schema.sql (the plain-SQL rendering for human
    # review) from the current models - also safe with no GCP access:
    .venv/bin/python scripts/bq_schema_sync.py --sql > ../bigquery/schema.sql

    # Once DB_BACKEND=bigquery and real GCP credentials are configured:
    .venv/bin/python scripts/bq_schema_sync.py
"""

from __future__ import annotations

import argparse

from app.main import create_app
from app.core.config import settings
from app.services.bq_schema import TableSchema, all_table_schemas, render_sql


def _print_plan(schemas: list[TableSchema]) -> None:
    for s in schemas:
        cluster = ", ".join(s.cluster_by) if s.cluster_by else "(none)"
        print(f"CREATE TABLE IF NOT EXISTS {settings.bigquery_dataset}.{s.name} ({len(s.fields)} columns) CLUSTER BY {cluster}")
        for note in s.notes:
            print(f"    - {note}")
    print(f"\n{len(schemas)} tables would be created/confirmed in dataset '{settings.bigquery_dataset}' (project '{settings.gcp_project_id}').")


def sync(*, dry_run: bool, sql: bool) -> None:
    schemas = all_table_schemas()

    if sql:
        print(render_sql(schemas, project=settings.gcp_project_id, dataset=settings.bigquery_dataset, location=settings.bigquery_location), end="")
        return

    if dry_run:
        _print_plan(schemas)
        return

    if settings.db_backend != "bigquery":
        raise SystemExit(
            "DB_BACKEND is not 'bigquery' - set it in .env (with real GCP_PROJECT_ID/"
            "BIGQUERY_DATASET/BIGQUERY_LOCATION and Application Default Credentials "
            "available), or pass --dry-run to just preview the plan."
        )

    from google.cloud import bigquery  # deferred: only needed for the real (non-dry-run) path

    from app.services.bq_schema import create_dataset, create_tables

    client = bigquery.Client(project=settings.gcp_project_id, location=settings.bigquery_location)
    dataset_ref = create_dataset(client, settings.gcp_project_id, settings.bigquery_dataset, settings.bigquery_location)
    print(f"Dataset {dataset_ref} ready ({settings.bigquery_location}).")

    for full_table_id, s in zip(create_tables(client, dataset_ref, schemas), schemas):
        print(f"  {full_table_id} ({len(s.fields)} columns, cluster_by={s.cluster_by or 'none'})")

    print(f"\n{len(schemas)} tables created/confirmed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Print the plan without touching GCP - safe with no credentials.")
    parser.add_argument("--sql", action="store_true", help="Print the full CREATE-TABLE DDL (bigquery/schema.sql's format) to stdout - safe with no credentials.")
    args = parser.parse_args()

    create_app()
    sync(dry_run=args.dry_run, sql=args.sql)
