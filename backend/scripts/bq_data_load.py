"""Loads *.jsonl files produced by scripts/bq_data_export.py into the
BigQuery tables scripts/bq_schema_sync.py already created.

Phase 6 (deferred/optional) of
/Users/Peeyush/.claude/plans/mossy-stirring-gosling.md. NOT yet run against a
real BigQuery project - no GCP access was available when this was written.
Run bq_schema_sync.py first so the target tables (and their exact column
types/clustering) already exist; this script appends into them rather than
inferring a schema, so a mismatch between the export and the live model
schema surfaces as a load-job error instead of silently picking the wrong
type.

Usage (once DB_BACKEND=bigquery and real credentials exist):
    .venv/bin/python scripts/bq_data_load.py --in-dir /tmp/simple_erp_export
"""

from __future__ import annotations

import argparse
from pathlib import Path

from app.core.config import settings


def run(in_dir: str) -> None:
    if settings.db_backend != "bigquery":
        raise SystemExit(
            "DB_BACKEND is not 'bigquery' - set it in .env (with real GCP_PROJECT_ID/"
            "BIGQUERY_DATASET/BIGQUERY_LOCATION and Application Default Credentials "
            "available) before running this script."
        )

    from google.cloud import bigquery

    client = bigquery.Client(project=settings.gcp_project_id, location=settings.bigquery_location)
    dataset_ref = bigquery.DatasetReference(settings.gcp_project_id, settings.bigquery_dataset)

    in_path = Path(in_dir)
    jsonl_files = sorted(in_path.glob("*.jsonl"))
    if not jsonl_files:
        raise SystemExit(f"no .jsonl files found in {in_path}")

    for file in jsonl_files:
        table_name = file.stem
        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
            # Uses the table's own already-created schema (bq_schema_sync.py)
            # rather than autodetect, so column types match exactly instead
            # of BigQuery guessing from the JSON values.
            autodetect=False,
        )
        with file.open("rb") as f:
            job = client.load_table_from_file(f, dataset_ref.table(table_name), job_config=job_config)
        job.result()
        print(f"  {table_name}: loaded {job.output_rows} row(s)" + (f" - errors: {job.errors}" if job.errors else ""))

    print(f"\n{len(jsonl_files)} table(s) loaded into {dataset_ref}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--in-dir", required=True, help="Directory containing <table>.jsonl files from bq_data_export.py")
    args = parser.parse_args()
    run(args.in_dir)
