"""Exports every table's current data from Postgres into newline-delimited
JSON files, one per table - ready for `bq load --source_format=
NEWLINE_DELIMITED_JSON` into the schemas scripts/bq_schema_sync.py creates.
Column names line up exactly since both read the same Base.metadata.

Phase 6 (deferred/optional) of
/Users/Peeyush/.claude/plans/mossy-stirring-gosling.md - only relevant if any
current Postgres data is worth preserving; fresh tables were the confirmed
choice for the initial cutover. Safe to run against the live dev database at
any time: read-only, writes nothing back to Postgres.

JSON (not CSV) so NUMERIC/TIMESTAMP/UUID/ARRAY/JSON column values round-trip
through `bq load` without a separate type-coercion pass.

Usage:
    .venv/bin/python scripts/bq_data_export.py --out-dir /tmp/simple_erp_export
    .venv/bin/python scripts/bq_data_export.py --out-dir /tmp/simple_erp_export --tables parties,products
"""

from __future__ import annotations

import argparse
import datetime
import decimal
import json
import uuid
from pathlib import Path

import sqlalchemy as sa

from app.main import create_app
from app.core.db import Base, session


def _json_default(value):
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, decimal.Decimal):
        return str(value)
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    raise TypeError(f"not JSON-serializable: {type(value).__name__} ({value!r})")


def export_table(table: sa.Table, out_dir: Path) -> int:
    out_path = out_dir / f"{table.name}.jsonl"
    count = 0
    with out_path.open("w") as f:
        result = session.execute(sa.select(table))
        for row in result.mappings():
            f.write(json.dumps(dict(row), default=_json_default))
            f.write("\n")
            count += 1
    return count


def run(out_dir: str, tables: list[str] | None) -> None:
    import app.models  # noqa: F401 - populates Base.metadata as a side effect

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    all_tables = list(Base.metadata.sorted_tables)
    if tables:
        wanted = set(tables)
        selected = [t for t in all_tables if t.name in wanted]
        missing = wanted - {t.name for t in selected}
        if missing:
            raise SystemExit(f"unknown table(s): {', '.join(sorted(missing))}")
        all_tables = selected

    total_rows = 0
    for table in all_tables:
        count = export_table(table, out_path)
        total_rows += count
        print(f"  {table.name}: {count} row(s) -> {out_path / f'{table.name}.jsonl'}")

    print(f"\n{len(all_tables)} table(s), {total_rows} row(s) exported to {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out-dir", required=True, help="Directory to write one <table>.jsonl file per table into.")
    parser.add_argument("--tables", help="Comma-separated table names to export (default: all).")
    args = parser.parse_args()

    create_app()
    run(args.out_dir, args.tables.split(",") if args.tables else None)
