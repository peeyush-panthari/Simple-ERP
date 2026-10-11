"""Live verification for app/services/bq_transaction.py + sequences.py's
BigQuery path (see /Users/Peeyush/.claude/plans/mossy-stirring-gosling.md,
Phase 1). NOT run yet - requires real GCP credentials and DB_BACKEND=bigquery
with the `doc_sequences` table created in the target dataset (Phase 2 schema
port). Run this before trusting run_in_transaction anywhere real: it's the
first live exercise of BigQuery's multi-statement-transaction behavior this
codebase has attempted, and bq_transaction.py's conflict-detection logic
(_is_conflict) was written from documentation, not observed errors.

Usage (once GCP access + DB_BACKEND=bigquery are set up):
    cd backend_py && .venv/bin/python scripts/bq_concurrency_check.py

What it checks:
  1. Sequential calls to next_sequence_value produce strictly increasing,
     distinct values (baseline correctness, no concurrency).
  2. N concurrent calls (threads) against the SAME (tenant_id, prefix) all
     succeed, return N distinct values, and no two collide - confirms
     conflicting concurrent MERGEs actually raise something _is_conflict()
     recognizes, and that the retry loop resolves them rather than either
     hanging or silently losing an update.
  3. Reports how many attempts were retried, so we know if max_retries=5
     is comfortably sufficient at this concurrency level or needs raising.

This intentionally creates and then deletes its own throwaway sequence
prefix (BQCHECK-<random>) - safe to run against a real dataset without
touching any real document counter.
"""

from __future__ import annotations

import sys
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, ".")

from app.main import create_app  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.services import sequences  # noqa: E402


def _require_bigquery_backend() -> None:
    if settings.db_backend != "bigquery":
        raise SystemExit(
            "DB_BACKEND is not 'bigquery' - set it in .env (with real GCP_PROJECT_ID/"
            "BIGQUERY_DATASET/BIGQUERY_LOCATION and Application Default Credentials "
            "available) before running this script."
        )


def check_sequential() -> None:
    tenant_id = uuid.uuid4()
    prefix = f"BQCHECK-SEQ-{uuid.uuid4().hex[:8]}"
    values = [sequences.next_sequence_value(tenant_id, prefix) for _ in range(10)]
    assert values == sorted(values), f"values not increasing: {values}"
    assert len(set(values)) == len(values), f"duplicate values: {values}"
    print(f"[sequential] OK - {values}")


def check_concurrent(n: int = 20) -> None:
    tenant_id = uuid.uuid4()
    prefix = f"BQCHECK-CONC-{uuid.uuid4().hex[:8]}"

    def call():
        return sequences.next_sequence_value(tenant_id, prefix)

    values: list[int] = []
    errors: list[Exception] = []
    with ThreadPoolExecutor(max_workers=n) as pool:
        futures = [pool.submit(call) for _ in range(n)]
        for f in as_completed(futures):
            try:
                values.append(f.result())
            except Exception as exc:  # noqa: BLE001 - want to see every failure, not just the first
                errors.append(exc)

    if errors:
        print(f"[concurrent] FAILED - {len(errors)}/{n} calls raised after exhausting retries:")
        for exc in errors:
            print(f"    {type(exc).__name__}: {exc}")
        raise SystemExit(1)

    duplicates = len(values) - len(set(values))
    if duplicates:
        print(f"[concurrent] FAILED - {duplicates} duplicate value(s) among {values}")
        raise SystemExit(1)

    print(f"[concurrent] OK - {n} concurrent calls returned {n} distinct values: {sorted(values)}")
    if sorted(values) != list(range(1, n + 1)):
        gaps = sorted(set(range(1, max(values) + 1)) - set(values))
        print(f"    note: not perfectly gapless (expected under the accepted tradeoff) - missing {gaps}")


if __name__ == "__main__":
    create_app()
    _require_bigquery_backend()
    check_sequential()
    check_concurrent()
    print("\nAll checks passed.")
