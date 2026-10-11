"""Reports how far the Postgres -> BigQuery cutover has got.

Counts are derived from the source, not hand-maintained, so this cannot drift
from reality the way a checklist in a doc does. Run it from backend/:

    .venv/bin/python scripts/bq_migration_status.py
    .venv/bin/python scripts/bq_migration_status.py --constraints

A module is "converted" when every Postgres write path in it has a `_bigquery`
counterpart: the plan's Phase 4 pairs each `_x_postgres` with an `_x_bigquery`
behind a `settings.db_backend` dispatcher, so counting those pairs against the
module's `session.commit()` sites measures real progress.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOMAINS = ROOT / "app" / "domains"
SERVICES = ROOT / "app" / "services"

_COMMIT_RE = re.compile(r"session\.commit\(\)")
_BQ_FN_RE = re.compile(r"^def\s+_(\w+)_bigquery\s*\(", re.MULTILINE)
_PG_FN_RE = re.compile(r"^def\s+_(\w+)_postgres\s*\(", re.MULTILINE)

# Phase 4's cutover order, simplest first. Modules not listed here are counted
# but reported under "unscheduled".
PHASE_4_TIERS = [
    # party types + product categories + business entities now live in the foundation domain.
    ("1. reference data", ["foundation/router", "foundation/masters_router", "system/router"]),
    ("2. master data", ["parties/router", "parties/children_router", "products/router", "bom/router", "warehouses/router"]),
    ("3. procurement -> warehouse -> inventory", ["procurement/router", "grn/router", "grn/qr_router", "inventory/router"]),
    ("4. orders -> finance -> logistics", ["orders/router", "finance/router", "logistics/router", "production/router"]),
    ("5. platform", ["identity/router", "notifications/router", "documents/router"]),
]


def scan(path: Path) -> tuple[int, int, int]:
    src = path.read_text()
    return len(_COMMIT_RE.findall(src)), len(set(_PG_FN_RE.findall(src))), len(set(_BQ_FN_RE.findall(src)))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--constraints", action="store_true", help="list the constraints BigQuery will not enforce")
    args = parser.parse_args()

    if args.constraints:
        return report_constraints()

    modules = {f"{p.parent.name}/{p.stem}": scan(p) for p in sorted(DOMAINS.glob("*/*.py")) if p.stem not in ("__init__", "schemas")}
    scheduled = {name for _, names in PHASE_4_TIERS for name in names}

    total_writes = total_done = 0
    for tier, names in PHASE_4_TIERS:
        print(f"\n{tier}")
        for name in names:
            if name not in modules:
                print(f"  {'-':>3}       {name} (no such module)")
                continue
            commits, _pg, bq = modules[name]
            total_writes += commits
            total_done += bq
            # Against commits, not against the _postgres count: a module part
            # way through the cutover has one of each named function but many
            # commit sites still unconverted, and comparing the two pair
            # counts would call that done.
            mark = "done" if bq >= commits else ("wip " if bq else "    ")
            print(f"  {mark} {bq:>2}/{commits:<3} {name}")

    unscheduled = sorted(set(modules) - scheduled)
    if unscheduled:
        print("\nunscheduled")
        for name in unscheduled:
            commits, _pg, bq = modules[name]
            total_writes += commits
            total_done += bq
            print(f"       {bq:>2}/{commits:<3} {name}")

    pct = (total_done / total_writes * 100) if total_writes else 0
    print(f"\nroute write paths on the BigQuery path: {total_done}/{total_writes} ({pct:.0f}%)")

    service_commits = sum(scan(p)[0] for p in SERVICES.glob("*.py"))
    print(f"service-layer write paths still Postgres-only: {service_commits}")
    return 0


def report_constraints() -> int:
    """Every constraint BigQuery drops, so app-level enforcement can be audited
    against it. Reads SQLAlchemy metadata only - no database connection."""
    sys.path.insert(0, str(ROOT))
    from app.services.bq_schema import all_table_schemas

    buckets: dict[str, list[str]] = {"UNIQUE": [], "CHECK": [], "other": []}
    for schema in all_table_schemas():
        for note in schema.notes:
            low = note.lower()
            key = "UNIQUE" if "unique" in low else "CHECK" if "check" in low else "other"
            buckets[key].append(f"{schema.name}: {note}")

    for key, entries in buckets.items():
        print(f"\n=== {key} ({len(entries)}) ===")
        for entry in entries:
            print(f"  {entry}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
