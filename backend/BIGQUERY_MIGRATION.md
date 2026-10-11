# Postgres → BigQuery cutover

Working notes for the migration described in
`~/.claude/plans/mossy-stirring-gosling.md`. Carried over unchanged in scope from the Flask app: the scaffolding is inert here too. BigQuery is the intended primary
OLTP store; `DB_BACKEND` stays `postgres` until Phase 4 is complete.

## Where it stands

Don't keep a checklist here — it goes stale. Ask the source:

```bash
.venv/bin/python scripts/bq_migration_status.py
```

Phases 0–3 (config, transaction primitive, schema derivation, write-script
builder) are in place. Phase 4, the module-by-module cutover, is the bulk of
the remaining work.

## Converting a module

Every write path becomes three functions and a dispatcher:

```python
def _create_thing_postgres(...) -> dict:   # unchanged
def _create_thing_bigquery(...) -> dict:   # new
def _create_thing(...):
    if settings.db_backend == "bigquery":
        return _create_thing_bigquery(...)
    return _create_thing_postgres(...)
```

Four rules the `_bigquery` half has to follow:

1. **Validation goes inside `build_ops()`, never above it.** `build_ops` is
   re-invoked on every retry, and that is the whole point: a transaction that
   lost a conflict must re-check against the latest committed state, not the
   snapshot it read on attempt one.
2. **Materialise every default.** BigQuery honours neither the model's Python
   `default=` nor its `server_default=`/`onupdate=`. `id`, `created_at`,
   `updated_at` and any defaulted column must be written explicitly, or the
   row lands with NULLs the Postgres path would never produce.
3. **Use `audit_insert_op()`, not a hand-built audit row.** It applies the
   same `_redact()` that `audit()` does; building the dict inline writes
   `meta` straight through and leaks whatever `_SENSITIVE_KEYS` covers.
4. **Build the response inside the closure.** There is no ORM row to
   re-serialise afterwards.

Test it by patching `run_write_transaction` in the route module and asserting
on the ops — see `tests/test_party_types_bigquery_path.py`. That runs offline;
the read-side checks still execute for real.

## What BigQuery stops enforcing

```bash
.venv/bin/python scripts/bq_migration_status.py --constraints
```

46 unique constraints and 237 check constraints disappear, and BigQuery
enforces no foreign keys. Every one of them that was the *only* guard now
needs an explicit app-level check in the write path. The ones already handled
are noted in each converted module's docstring; the rest are outstanding.

Two consequences worth stating plainly, because they change behaviour rather
than just moving enforcement:

- **Duplicate rows become reachable under concurrency.** The app-level check
  and the insert are in one BigQuery transaction, so a conflicting pair should
  abort and retry — but that depends entirely on the conflict detection below
  actually working.
- **Document numbering is no longer gapless** (`sequences.py:12`). Numbers stay
  distinct, but an aborted attempt burns one. Worth confirming with your
  accountant against the GST requirement for consecutive invoice serials
  before this reaches real invoices.

## Blocked on GCP access

Nothing here has ever run against a real BigQuery dataset. Two specific risks
stay unverified until it does, and both are load-bearing:

1. **`bq_transaction._is_conflict()` is a guess.** It matches
   `google.api_core.exceptions.Aborted` plus three message substrings. If
   BigQuery actually raises something else for a transaction conflict, every
   retry path silently degrades into "raise immediately" — and the retry is
   what replaces the row locks this migration removed. `scripts/bq_concurrency_check.py`
   exists to settle this; it needs a live dataset.
2. **ORM reads through `sqlalchemy-bigquery` are assumed to work.** Phase 3
   keeps all 245 `.query.` call sites on the dialect. Some of them use
   `db.func.upper()`, `.count()`, and filtered joins that have not been
   exercised against the dialect at all.

To unblock, from a machine with access to the project:

```bash
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

then set `GCP_PROJECT_ID` and `BIGQUERY_DATASET` in `.env` and run
`scripts/bq_schema_sync.py` followed by `scripts/bq_concurrency_check.py`.
