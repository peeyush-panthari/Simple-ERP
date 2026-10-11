"""Runs a BigQuery multi-statement script as one atomic transaction, with
retry-on-conflict standing in for the row/advisory locks this migration
removes (inventory_ledger.lock_stock, procurement_repo.lock_po,
bom_repo.lock_bom - still Postgres-only; each is ported when its own module
is cut over in Phase 4, not here).

BigQuery has no row-level locking: two concurrent transactions mutating the
same rows don't queue the way Postgres's locks did. Instead a conflicting
concurrent transaction fails at COMMIT with an optimistic-concurrency error,
and the caller is expected to retry. That's what this module does.

The full read-check-write sequence for one logical operation must be a
single self-contained SQL script (BEGIN TRANSACTION ... COMMIT TRANSACTION),
rebuilt from scratch on every attempt so a retry re-reads the latest
committed state - not a sequence of separate Python-level calls interleaved
with business logic, which BigQuery's scripting model does not support the
way a long-lived Postgres transaction did.

See /Users/Peeyush/.claude/plans/mossy-stirring-gosling.md (Phase 1). This is
implemented against Google's documented multi-statement-transaction behavior
but has NOT been exercised against a real BigQuery dataset - no GCP
credentials were available while this was written. Run
scripts/bq_concurrency_check.py against a live dataset before trusting this
anywhere real, specifically to confirm the exact exception type/message
BigQuery raises for a transaction conflict (_is_conflict below is a
best-effort guess at that until then).
"""

from __future__ import annotations

import logging
import random
import time
from typing import Callable

from google.api_core.exceptions import Aborted, BadRequest, GoogleAPICallError
from google.cloud import bigquery
from google.cloud.bigquery.table import RowIterator

from app.core.config import settings

logger = logging.getLogger("axon.bq_transaction")

_BASE_DELAY_SECONDS = 0.25
_MAX_DELAY_SECONDS = 4.0

# BigQuery's documented error for a transaction aborted by a concurrent
# conflicting mutation is google.api_core.exceptions.Aborted (gRPC ABORTED /
# HTTP 409). These message substrings are a fallback for conflict variants
# that may surface as a 400 BadRequest instead - unverified without a live
# dataset, kept narrow so we don't accidentally retry a genuine bad-request.
_CONFLICT_MESSAGE_HINTS = ("concurrent update", "could not serialize", "transaction is aborted")

_client: bigquery.Client | None = None


def _get_client() -> bigquery.Client:
    global _client
    if _client is None:
        _client = bigquery.Client(project=settings.gcp_project_id, location=settings.bigquery_location)
    return _client


def _is_conflict(exc: GoogleAPICallError) -> bool:
    if isinstance(exc, Aborted):
        return True
    if isinstance(exc, BadRequest):
        message = str(exc).lower()
        return any(hint in message for hint in _CONFLICT_MESSAGE_HINTS)
    return False


def run_in_transaction(
    build_script: Callable[[], tuple[str, list[bigquery.ScalarQueryParameter]]],
    *,
    max_retries: int = 5,
) -> RowIterator:
    """Executes `build_script()`'s (sql, params) as one BigQuery script job,
    retrying the whole thing - script rebuilt from scratch each attempt - on
    a detected concurrency conflict. `sql` must be a complete script
    including its own `BEGIN TRANSACTION` / `COMMIT TRANSACTION` (raise an
    app-level error inside the script with `RAISE USING MESSAGE = '...'` to
    roll back on a business-rule failure, e.g. insufficient stock).

    Returns the row iterator for the script's final result-producing
    statement. Raises the original exception once max_retries is exhausted,
    or immediately for any non-conflict error.
    """
    client = _get_client()
    last_error: GoogleAPICallError | None = None
    for attempt in range(max_retries):
        sql, params = build_script()
        job_config = bigquery.QueryJobConfig(query_parameters=params)
        try:
            job = client.query(sql, job_config=job_config)
            return job.result()
        except GoogleAPICallError as exc:
            if not _is_conflict(exc):
                raise
            last_error = exc
            delay = min(_MAX_DELAY_SECONDS, _BASE_DELAY_SECONDS * (2**attempt)) * (0.5 + random.random())
            logger.warning(
                "BigQuery transaction conflict (attempt %s/%s): %s - retrying in %.2fs",
                attempt + 1,
                max_retries,
                exc,
                delay,
            )
            time.sleep(delay)
    assert last_error is not None
    raise last_error
